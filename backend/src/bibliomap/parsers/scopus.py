"""Scopus CSV export parser.

Scopus changed its author separator over time: older exports use
``Smith J., Doe A.B.`` while newer ones use ``Smith J.; Doe A.B.``. Both are
supported. Placeholder values such as ``[No abstract available]`` are dropped.
"""

from __future__ import annotations

import re

from bibliomap.parsers._common import (
    clean,
    dedupe,
    format_issn,
    map_document_type,
    normalize_doi,
    parse_int,
    parse_year,
    read_csv,
    split_list,
)
from bibliomap.schema import Author, ParseResult, ParseWarning, Record, SourceFormat

_OLD_AUTHOR_SEP = re.compile(r"(?<=\.),\s+")
_SCOPUS_AUTHOR_ID = re.compile(r"\s*\(\d+\)$")
_PLACEHOLDER = re.compile(r"^\[No .+ available\]$", re.IGNORECASE)


def _get(row: dict[str, str], column: str) -> str | None:
    value = clean(row.get(column))
    if value is None or _PLACEHOLDER.match(value):
        return None
    return value


def _split_authors(value: str | None) -> list[str]:
    if not value:
        return []
    if ";" in value:
        return split_list(value)
    return [a for a in (clean(p) for p in _OLD_AUTHOR_SEP.split(value)) if a]


def _author_affiliation(entry: str, short_name: str) -> str | None:
    """Strip the leading author name from an 'Authors with affiliations' entry."""
    entry = entry.strip()
    for prefix in (f"{short_name}, ", f"{short_name.rstrip('.')}, "):
        if entry.startswith(prefix):
            return clean(entry[len(prefix) :])
    return None


def _build_authors(row: dict[str, str]) -> list[Author]:
    short_names = _split_authors(_get(row, "Authors"))
    full_names = [_SCOPUS_AUTHOR_ID.sub("", n) for n in split_list(_get(row, "Author full names"))]
    with_affils = split_list(_get(row, "Authors with affiliations"))

    authors: list[Author] = []
    for i, short in enumerate(short_names):
        affiliation = None
        if i < len(with_affils):
            affiliation = _author_affiliation(with_affils[i], short)
        authors.append(
            Author(
                name=short,
                full_name=full_names[i] if i < len(full_names) else None,
                affiliations=[affiliation] if affiliation else [],
            )
        )
    return authors


def _to_record(row: dict[str, str]) -> Record | None:
    title = _get(row, "Title")
    if not title:
        return None
    doc_type_raw = _get(row, "Document Type")
    return Record(
        source_format=SourceFormat.SCOPUS,
        source_id=_get(row, "EID"),
        title=title,
        authors=_build_authors(row),
        year=parse_year(_get(row, "Year")),
        source_title=_get(row, "Source title"),
        source_abbrev=_get(row, "Abbreviated Source Title"),
        document_type=map_document_type(doc_type_raw),
        document_type_raw=doc_type_raw,
        abstract=_get(row, "Abstract"),
        doi=normalize_doi(_get(row, "DOI")),
        pmid=_get(row, "PubMed ID"),
        issn=format_issn(split_list(_get(row, "ISSN"))),
        volume=_get(row, "Volume"),
        issue=_get(row, "Issue"),
        page_start=_get(row, "Page start"),
        page_end=_get(row, "Page end"),
        article_number=_get(row, "Art. No."),
        language=_get(row, "Language of Original Document"),
        publisher=_get(row, "Publisher"),
        author_keywords=dedupe(split_list(_get(row, "Author Keywords"))),
        index_keywords=dedupe(split_list(_get(row, "Index Keywords"))),
        affiliations=dedupe(split_list(_get(row, "Affiliations"))),
        cited_by=parse_int(_get(row, "Cited by")),
        references=split_list(_get(row, "References")),
        url=_get(row, "Link"),
    )


def parse_scopus(text: str) -> ParseResult:
    reader = read_csv(text)

    warnings: list[ParseWarning] = []
    if "Title" not in (reader.fieldnames or []):
        warnings.append(
            ParseWarning(message="Kolom 'Title' tidak ditemukan; bukan file CSV Scopus?")
        )
        return ParseResult(source_format=SourceFormat.SCOPUS, records=[], warnings=warnings)

    records: list[Record] = []
    for index, row in enumerate(reader):
        record = _to_record(row)
        if record is None:
            warnings.append(ParseWarning(record_index=index, message="Baris tanpa judul (Title)."))
            continue
        records.append(record)
    return ParseResult(source_format=SourceFormat.SCOPUS, records=records, warnings=warnings)
