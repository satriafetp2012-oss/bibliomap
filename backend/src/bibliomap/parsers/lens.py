"""Lens.org scholarly works CSV export parser.

Lens writes author names in natural order ("Jason R. C. Nurse"), separates
multi-valued cells with ``; `` and lists references as Lens IDs.
"""

from __future__ import annotations

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


def _get(row: dict[str, str], column: str) -> str | None:
    return clean(row.get(column))


def _to_record(row: dict[str, str]) -> Record | None:
    title = _get(row, "Title")
    if not title:
        return None
    doc_type_raw = _get(row, "Publication Type")
    return Record(
        source_format=SourceFormat.LENS,
        source_id=_get(row, "Lens ID"),
        title=title,
        authors=[Author(name=name, full_name=name) for name in split_list(_get(row, "Author/s"))],
        year=parse_year(_get(row, "Publication Year") or _get(row, "Date Published")),
        source_title=_get(row, "Source Title"),
        document_type=map_document_type(doc_type_raw),
        document_type_raw=doc_type_raw,
        abstract=_get(row, "Abstract"),
        doi=normalize_doi(_get(row, "DOI")),
        pmid=_get(row, "PMID"),
        issn=format_issn(split_list(_get(row, "ISSNs"))),
        volume=_get(row, "Volume"),
        issue=_get(row, "Issue Number"),
        page_start=_get(row, "Start Page"),
        page_end=_get(row, "End Page"),
        publisher=_get(row, "Publisher"),
        author_keywords=dedupe(split_list(_get(row, "Keywords"))),
        # Fields of Study are Lens-assigned; MeSH terms come from PubMed.
        index_keywords=dedupe(
            split_list(_get(row, "Fields of Study")) + split_list(_get(row, "MeSH Terms"))
        ),
        cited_by=parse_int(_get(row, "Citing Works Count")),
        references=split_list(_get(row, "References")),
        url=_get(row, "External URL"),
    )


def parse_lens(text: str) -> ParseResult:
    reader = read_csv(text)
    warnings: list[ParseWarning] = []
    if "Lens ID" not in (reader.fieldnames or []):
        warnings.append(ParseWarning(message="Kolom 'Lens ID' tidak ditemukan; bukan CSV Lens?"))
        return ParseResult(source_format=SourceFormat.LENS, records=[], warnings=warnings)

    records: list[Record] = []
    for index, row in enumerate(reader):
        record = _to_record(row)
        if record is None:
            warnings.append(ParseWarning(record_index=index, message="Baris tanpa judul (Title)."))
            continue
        records.append(record)
    return ParseResult(source_format=SourceFormat.LENS, records=records, warnings=warnings)
