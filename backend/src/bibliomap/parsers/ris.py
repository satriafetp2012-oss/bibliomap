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
    parse_year,
)
from bibliomap.schema import Author, ParseResult, ParseWarning, Record, SourceFormat

_TAG_LINE = re.compile(r"^([A-Z][A-Z0-9])  -(?: (.*))?$")

RawRecord = dict[str, list[str]]

# Tag precedence: the first tag present wins.
_TITLE_TAGS = ("TI", "T1")
_SOURCE_TAGS = ("T2", "JF", "JO", "BT")
_ABBREV_TAGS = ("J2", "JA")
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


def _to_record(raw: RawRecord) -> Record | None:
    title = _first(raw, _TITLE_TAGS)
    if not title:
        return None
    authors = [Author(name=name) for tag in _AUTHOR_TAGS for name in _all(raw, tag)]
    doc_type_raw = _first(raw, ("TY",))
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
        source_title=_first(raw, _SOURCE_TAGS),
        source_abbrev=_first(raw, _ABBREV_TAGS),
        document_type=map_document_type(doc_type_raw),
        document_type_raw=doc_type_raw,
        abstract=_first(raw, _ABSTRACT_TAGS),
        doi=doi,
        issn=_all(raw, "SN"),
        volume=_first(raw, ("VL",)),
        issue=_first(raw, ("IS",)),
        page_start=_first(raw, ("SP",)),
        page_end=_first(raw, ("EP",)),
        language=_first(raw, ("LA",)),
        publisher=_first(raw, ("PB",)),
        author_keywords=dedupe(_all(raw, "KW")),
        affiliations=dedupe(_all(raw, "AD")),
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
