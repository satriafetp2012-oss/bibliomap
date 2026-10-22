"""OpenAlex web-interface CSV export parser.

Columns are flattened JSON paths (``authorships.author.display_name``) and
list values are joined with ``|``. The set of columns varies with the export
settings, so every column is optional except ``id`` and a title.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from bibliomap.parsers._common import (
    clean,
    dedupe,
    map_document_type,
    normalize_doi,
    parse_int,
    parse_year,
    read_csv,
    split_list,
)
from bibliomap.schema import Author, ParseResult, ParseWarning, Record, SourceFormat

_TAG = re.compile(r"<[^>]+>")
_OPENALEX_PREFIX = "https://openalex.org/"


def is_openalex_csv(fieldnames: Sequence[str]) -> bool:
    names = set(fieldnames)
    return (
        "id" in names
        and bool(names & {"display_name", "title"})
        and any(n.startswith(("authorships.", "primary_location.")) for n in names)
    )


def _get(row: dict[str, str], *columns: str) -> str | None:
    for column in columns:
        if value := clean(row.get(column)):
            return value
    return None


def _pipe(row: dict[str, str], column: str) -> list[str]:
    """Split a '|'-joined cell, keeping empty slots so lists stay aligned."""
    value = row.get(column)
    return [part.strip() for part in value.split("|")] if value else []


def _authors(row: dict[str, str]) -> list[Author]:
    names = _pipe(row, "authorships.author.display_name")
    orcids = _pipe(row, "authorships.author.orcid")
    # ORCIDs can only be paired with names when both lists line up.
    aligned = len(orcids) == len(names)
    authors: list[Author] = []
    for i, name in enumerate(names):
        if not name:
            continue
        orcid = orcids[i] if aligned else ""
        authors.append(
            Author(
                name=name,
                full_name=name,
                orcid=orcid.removeprefix("https://orcid.org/") or None,
            )
        )
    return authors


def _to_record(row: dict[str, str]) -> Record | None:
    title = clean(_TAG.sub("", _get(row, "display_name", "title") or ""))
    if not title:
        return None
    pmid = _get(row, "ids.pmid")
    doc_type_raw = _get(row, "type")
    issn = [i for i in _pipe(row, "primary_location.source.issn") if i] or [
        i for i in [_get(row, "primary_location.source.issn_l")] if i
    ]
    affiliations = [a for a in _pipe(row, "authorships.institutions.display_name") if a] or [
        a for a in _pipe(row, "authorships.raw_affiliation_strings") if a
    ]
    return Record(
        source_format=SourceFormat.OPENALEX,
        source_id=(_get(row, "id") or "").removeprefix(_OPENALEX_PREFIX) or None,
        title=title,
        authors=_authors(row),
        year=parse_year(_get(row, "publication_year", "publication_date")),
        source_title=_get(row, "primary_location.source.display_name"),
        document_type=map_document_type(doc_type_raw),
        document_type_raw=doc_type_raw,
        abstract=_get(row, "abstract"),
        doi=normalize_doi(_get(row, "doi")),
        pmid=pmid.rstrip("/").rsplit("/", 1)[-1] if pmid else None,
        issn=dedupe(issn),
        volume=_get(row, "biblio.volume"),
        issue=_get(row, "biblio.issue"),
        page_start=_get(row, "biblio.first_page"),
        page_end=_get(row, "biblio.last_page"),
        language=_get(row, "language"),
        publisher=_get(row, "primary_location.source.host_organization_name"),
        index_keywords=dedupe([k for k in _pipe(row, "keywords.display_name") if k]),
        affiliations=dedupe(affiliations),
        cited_by=parse_int(_get(row, "cited_by_count")),
        references=[
            r.removeprefix(_OPENALEX_PREFIX) for r in split_list(row.get("referenced_works"), "|")
        ],
        url=_get(row, "primary_location.landing_page_url"),
    )


def parse_openalex_csv(text: str) -> ParseResult:
    reader = read_csv(text)
    warnings: list[ParseWarning] = []
    if not is_openalex_csv(reader.fieldnames or []):
        warnings.append(ParseWarning(message="Kolom OpenAlex (id, display_name) tidak ditemukan."))
        return ParseResult(source_format=SourceFormat.OPENALEX, records=[], warnings=warnings)

    records: list[Record] = []
    for index, row in enumerate(reader):
        record = _to_record(row)
        if record is None:
            warnings.append(ParseWarning(record_index=index, message="Baris tanpa judul."))
            continue
        records.append(record)
    return ParseResult(source_format=SourceFormat.OPENALEX, records=records, warnings=warnings)
