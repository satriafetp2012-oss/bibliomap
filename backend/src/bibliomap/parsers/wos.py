"""Web of Science "Plain text" (tagged) export parser.

Format: each line starts with a two-character tag and a space; lines that
start with three spaces continue the previous tag. ``ER`` closes a record and
``EF`` closes the file. For list fields (AU, AF, CR, C1) every line is a new
item; for text fields (TI, AB, DE, ...) continuation lines are wrapped text.
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
    split_list,
)
from bibliomap.schema import Author, ParseResult, ParseWarning, Record, SourceFormat

_TAG_LINE = re.compile(r"^([A-Z][A-Z0-9]) ?(.*)$")
# C1 line with explicit authors: "[Smith, J; Doe, A] Univ X, Dept Y, City, Country."
_C1_WITH_AUTHORS = re.compile(r"^\[(?P<authors>[^\]]+)\]\s*(?P<affil>.+)$")
# OI / RI entries: "Smith, John/0000-0002-1825-0097"
_ORCID_ENTRY = re.compile(r"^(?P<name>.+?)/(?P<id>\d{4}-\d{4}-\d{4}-\d{3}[\dX])$")

RawRecord = dict[str, list[str]]


def _tokenize(text: str) -> list[RawRecord]:
    """Group tag lines into raw records (tag -> list of line values)."""
    records: list[RawRecord] = []
    current: RawRecord = {}
    last_tag: str | None = None

    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("   ") and last_tag:
            current.setdefault(last_tag, []).append(line.strip())
            continue
        match = _TAG_LINE.match(line.lstrip("\ufeff"))
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag in ("FN", "VR", "EF"):
            last_tag = None
            continue
        if tag == "ER":
            if current:
                records.append(current)
            current, last_tag = {}, None
            continue
        current.setdefault(tag, []).append(value)
        last_tag = tag

    # Tolerate a truncated file whose last record has no ER line.
    if current:
        records.append(current)
    return records


def _text(raw: RawRecord, tag: str) -> str | None:
    return clean(" ".join(raw.get(tag, [])))


def _keywords(raw: RawRecord, tag: str) -> list[str]:
    return dedupe(split_list(_text(raw, tag)))


def _parse_affiliations(raw: RawRecord) -> tuple[list[str], dict[str, list[str]]]:
    """Return all affiliation strings and a map of author name -> affiliations."""
    all_affils: list[str] = []
    by_author: dict[str, list[str]] = {}
    for line in raw.get("C1", []):
        match = _C1_WITH_AUTHORS.match(line)
        affil = clean(match.group("affil") if match else line)
        if not affil:
            continue
        affil = affil.rstrip(".")
        all_affils.append(affil)
        if match:
            for name in split_list(match.group("authors")):
                by_author.setdefault(name, []).append(affil)
    return dedupe(all_affils), by_author


def _parse_orcids(raw: RawRecord) -> dict[str, str]:
    orcids: dict[str, str] = {}
    for entry in split_list(_text(raw, "OI")):
        match = _ORCID_ENTRY.match(entry)
        if match:
            orcids[match.group("name").strip()] = match.group("id")
    return orcids


def _build_authors(raw: RawRecord) -> list[Author]:
    short_names = [n for n in raw.get("AU", []) if n]
    full_names = [n for n in raw.get("AF", []) if n]
    _, affils_by_author = _parse_affiliations(raw)
    orcids = _parse_orcids(raw)

    authors: list[Author] = []
    for i, short in enumerate(short_names):
        full = full_names[i] if i < len(full_names) else None
        # C1 brackets and OI use the full name when AF exists.
        key = full or short
        authors.append(
            Author(
                name=short,
                full_name=full,
                orcid=orcids.get(key),
                affiliations=affils_by_author.get(key, []),
            )
        )
    return authors


def _to_record(raw: RawRecord) -> Record | None:
    title = _text(raw, "TI")
    if not title:
        return None
    affiliations, _ = _parse_affiliations(raw)
    doc_type_raw = _text(raw, "DT")
    return Record(
        source_format=SourceFormat.WOS,
        source_id=_text(raw, "UT"),
        title=title,
        authors=_build_authors(raw),
        year=parse_year(_text(raw, "PY")),
        source_title=_text(raw, "SO"),
        source_abbrev=_text(raw, "J9") or _text(raw, "JI"),
        # DT may hold "Article; Early Access"; the first label is the type.
        document_type=map_document_type(*split_list(doc_type_raw)),
        document_type_raw=doc_type_raw,
        abstract=_text(raw, "AB"),
        doi=normalize_doi(_text(raw, "DI")),
        pmid=_text(raw, "PM"),
        issn=[v for v in (_text(raw, "SN"), _text(raw, "EI")) if v],
        volume=_text(raw, "VL"),
        issue=_text(raw, "IS"),
        page_start=_text(raw, "BP"),
        page_end=_text(raw, "EP"),
        article_number=_text(raw, "AR"),
        language=_text(raw, "LA"),
        publisher=_text(raw, "PU"),
        author_keywords=_keywords(raw, "DE"),
        index_keywords=_keywords(raw, "ID"),
        affiliations=affiliations,
        # Z9 = times cited across all WoS databases; TC = Core Collection only.
        cited_by=parse_int(_text(raw, "TC")),
        references=[ref for ref in raw.get("CR", []) if ref],
    )


def parse_wos(text: str) -> ParseResult:
    records: list[Record] = []
    warnings: list[ParseWarning] = []
    for index, raw in enumerate(_tokenize(text)):
        record = _to_record(raw)
        if record is None:
            warnings.append(ParseWarning(record_index=index, message="Rekaman tanpa judul (TI)."))
            continue
        records.append(record)
    return ParseResult(source_format=SourceFormat.WOS, records=records, warnings=warnings)
