"""PubMed MEDLINE (.nbib / "PubMed format") export parser.

Format: a tag left-justified in four columns, then ``- `` and the value.
Lines starting with six spaces continue the previous value. ``PMID`` opens a
record. Field order matters: ``AD`` and ``AUID`` belong to the preceding
``FAU``/``AU`` author.
"""

from __future__ import annotations

import re

from bibliomap.parsers._common import (
    clean,
    dedupe,
    expand_page_range,
    map_document_type,
    normalize_doi,
    parse_year,
)
from bibliomap.schema import Author, ParseResult, ParseWarning, Record, SourceFormat

_TAG_LINE = re.compile(r"^([A-Z][A-Z0-9]{0,3}) {0,3}- ?(.*)$")
_ORCID = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")
# "10.1000/xyz [doi]" in LID / AID
_TYPED_ID = re.compile(r"^(?P<value>.+?)\s*\[(?P<kind>[a-z]+)\]$")
# "1234-5678 (Electronic)" in IS
_ISSN = re.compile(r"\b(\d{4}-\d{3}[\dX])\b")

Field = tuple[str, str]


def _tokenize(text: str) -> list[list[Field]]:
    """Return records as ordered (tag, value) lists, joining wrapped lines."""
    records: list[list[Field]] = []
    current: list[Field] = []

    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("      ") and current:
            tag, value = current[-1]
            current[-1] = (tag, f"{value} {line.strip()}")
            continue
        match = _TAG_LINE.match(line.lstrip("\ufeff"))
        if not match:
            continue
        tag, value = match.group(1), match.group(2).strip()
        if tag == "PMID" and current:
            records.append(current)
            current = []
        current.append((tag, value))

    if current:
        records.append(current)
    return records


def _values(fields: list[Field], tag: str) -> list[str]:
    return [v for t, raw in fields if t == tag and (v := clean(raw))]


def _first(fields: list[Field], tag: str) -> str | None:
    values = _values(fields, tag)
    return values[0] if values else None


def _build_authors(fields: list[Field]) -> list[Author]:
    """Walk fields in order so AD/AUID attach to the author just before them."""
    authors: list[Author] = []
    has_fau = any(tag == "FAU" for tag, _ in fields)
    for tag, raw in fields:
        value = clean(raw)
        if not value:
            continue
        if tag == "FAU":
            authors.append(Author(name=value, full_name=value))
        elif tag == "AU":
            if has_fau:
                # AU follows its FAU and carries the short form ("Smith J").
                if authors and authors[-1].name == authors[-1].full_name:
                    authors[-1].name = value
            else:
                authors.append(Author(name=value))
        elif tag == "AD" and authors:
            authors[-1].affiliations.append(value)
        elif tag == "AUID" and authors and (match := _ORCID.search(value)):
            authors[-1].orcid = match.group(1)
    return authors


def _doi(fields: list[Field]) -> str | None:
    for tag in ("LID", "AID"):
        for value in _values(fields, tag):
            match = _TYPED_ID.match(value)
            if match and match.group("kind") == "doi":
                return normalize_doi(match.group("value"))
    return None


def _to_record(fields: list[Field]) -> Record | None:
    title = _first(fields, "TI") or _first(fields, "BTI")
    if not title:
        return None
    authors = _build_authors(fields)
    publication_types = _values(fields, "PT")
    page_start, page_end = expand_page_range(_first(fields, "PG"))
    issn = dedupe([m.group(1) for v in _values(fields, "IS") if (m := _ISSN.search(v))])
    return Record(
        source_format=SourceFormat.PUBMED,
        source_id=_first(fields, "PMID"),
        # MEDLINE titles end with a period that is not part of the title.
        title=title.removesuffix("."),
        authors=authors,
        year=parse_year(_first(fields, "DP")),
        source_title=_first(fields, "JT"),
        source_abbrev=_first(fields, "TA"),
        document_type=map_document_type(*publication_types),
        document_type_raw="; ".join(publication_types) or None,
        abstract=_first(fields, "AB"),
        doi=_doi(fields),
        pmid=_first(fields, "PMID"),
        issn=issn,
        volume=_first(fields, "VI"),
        issue=_first(fields, "IP"),
        page_start=page_start,
        page_end=page_end,
        language=_first(fields, "LA"),
        author_keywords=dedupe(_values(fields, "OT")),
        # MeSH headings: drop qualifiers ("Humans/*epidemiology" -> "Humans").
        index_keywords=dedupe([v.split("/")[0].lstrip("*") for v in _values(fields, "MH")]),
        affiliations=dedupe([a for author in authors for a in author.affiliations]),
    )


def parse_pubmed(text: str) -> ParseResult:
    records: list[Record] = []
    warnings: list[ParseWarning] = []
    for index, fields in enumerate(_tokenize(text)):
        record = _to_record(fields)
        if record is None:
            warnings.append(ParseWarning(record_index=index, message="Rekaman tanpa judul (TI)."))
            continue
        records.append(record)
    return ParseResult(source_format=SourceFormat.PUBMED, records=records, warnings=warnings)
