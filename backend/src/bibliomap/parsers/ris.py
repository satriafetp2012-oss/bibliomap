"""RIS parser (EndNote, Zotero, Mendeley, Scopus and WoS RIS exports).

Format: ``TG  - value`` with a two-character tag, two spaces, a dash and a
space. ``TY`` opens a record and ``ER`` closes it. Lines without a tag are
treated as continuations of the previous value.
"""

from __future__ import annotations

import re

from bibliomap.parsers._common import (
    clean,
    dedupe,
    map_document_type,
    normalize_doi,
    parse_int,
    parse_year,
)
from bibliomap.schema import Author, ParseResult, ParseWarning, Record, SourceFormat

_TAG_LINE = re.compile(r"^([A-Z][A-Z0-9])  -(?: (.*))?$")

RawRecord = dict[str, list[str]]

# Tag precedence: the first tag present wins.
_TITLE_TAGS = ("TI", "T1")
# EMBASE puts the journal in JF and uses T2 for conference names; WoS and
# Scopus put the journal in T2; ScienceDirect uses JO, or BT for books.
_SOURCE_TAGS = ("JF", "T2", "JO", "BT")
_ABBREV_TAGS = ("J2", "JA", "J9", "JI")

# Citation counts hidden in N1 notes.
_CITED_BY_NOTE = re.compile(
    r"(?:Times Cited in Web of Science Core Collection|Cited By):\s*(\d+)", re.IGNORECASE
)
_YEAR_TAGS = ("PY", "Y1", "DA")
_ABSTRACT_TAGS = ("AB", "N2")
_AUTHOR_TAGS = ("AU", "A1")


def _tokenize(text: str) -> list[RawRecord]:
    records: list[RawRecord] = []
    current: RawRecord | None = None
    last_tag: str | None = None

    for line in text.splitlines():
        if not line.strip():
            continue
        match = _TAG_LINE.match(line.lstrip("\ufeff"))
        if not match:
            # Continuation of a wrapped value.
            if current is not None and last_tag and current.get(last_tag):
                current[last_tag][-1] += " " + line.strip()
            continue
        tag, value = match.group(1), (match.group(2) or "").strip()
        if tag == "TY":
            current, last_tag = {"TY": [value]}, "TY"
            continue
        if current is None:
            continue
        if tag == "ER":
            records.append(current)
            current, last_tag = None, None
            continue
        current.setdefault(tag, []).append(value)
        last_tag = tag

    if current is not None:
        records.append(current)
    return records


def _first(raw: RawRecord, tags: tuple[str, ...]) -> str | None:
    for tag in tags:
        for value in raw.get(tag, []):
            if cleaned := clean(value):
                return cleaned
    return None


def _all(raw: RawRecord, tag: str) -> list[str]:
    return [v for v in (clean(x) for x in raw.get(tag, [])) if v]


def _title(raw: RawRecord) -> tuple[str | None, str | None]:
    """Return (title, tag used). Falls back for exporters that omit TI/T1."""
    if title := _first(raw, _TITLE_TAGS):
        return title, None
    # EMBASE: a record without T1 keeps its title in T2 when JF holds the journal.
    if (raw.get("JF") or raw.get("JO")) and (title := _first(raw, ("T2",))):
        return title, "T2"
    # ScienceDirect whole-book entries carry only the book title.
    if title := _first(raw, ("BT",)):
        return title, "BT"
    return None, None


def _cited_by(raw: RawRecord) -> int | None:
    for note in raw.get("N1", []):
        if match := _CITED_BY_NOTE.search(note):
            return parse_int(match.group(1))
    return None


def _to_record(raw: RawRecord) -> Record | None:
    title, title_tag = _title(raw)
    if not title:
        return None
    source_tags = tuple(tag for tag in _SOURCE_TAGS if tag != title_tag)
    authors = [Author(name=name) for tag in _AUTHOR_TAGS for name in _all(raw, tag)]
    # Scopus refines TY with M3 (e.g. TY JOUR + M3 Review).
    doc_type_raw = _first(raw, ("M3",)) or _first(raw, ("TY",))
    doi = normalize_doi(_first(raw, ("DO",)))
    if doi is None:
        # Some exporters put the DOI only in UR or M3.
        doi = next((d for v in _all(raw, "UR") if (d := normalize_doi(v))), None)
    return Record(
        source_format=SourceFormat.RIS,
        source_id=_first(raw, ("AN", "ID")),
        title=title,
        authors=authors,
        year=parse_year(_first(raw, _YEAR_TAGS)),
        source_title=_first(raw, source_tags),
        source_abbrev=_first(raw, _ABBREV_TAGS),
        document_type=map_document_type(_first(raw, ("M3",)), _first(raw, ("TY",))),
        document_type_raw=doc_type_raw,
        abstract=_first(raw, _ABSTRACT_TAGS),
        doi=doi,
        issn=_all(raw, "SN"),
        volume=_first(raw, ("VL",)),
        issue=_first(raw, ("IS",)),
        page_start=_first(raw, ("SP",)),
        page_end=_first(raw, ("EP",)),
        article_number=_first(raw, ("C7",)),
        language=_first(raw, ("LA",)),
        publisher=_first(raw, ("PB", "PU")),
        author_keywords=dedupe(_all(raw, "KW")),
        affiliations=dedupe(_all(raw, "AD")),
        cited_by=_cited_by(raw),
        # WoS RIS exports carry cited references as CR lines.
        references=_all(raw, "CR"),
        url=_first(raw, ("UR",)),
    )


def parse_ris(text: str) -> ParseResult:
    records: list[Record] = []
    warnings: list[ParseWarning] = []
    for index, raw in enumerate(_tokenize(text)):
        record = _to_record(raw)
        if record is None:
            warnings.append(
                ParseWarning(record_index=index, message="Rekaman tanpa judul (TI/T1).")
            )
            continue
        records.append(record)
    return ParseResult(source_format=SourceFormat.RIS, records=records, warnings=warnings)
