"""Map OpenAlex work objects to canonical records."""

from __future__ import annotations

import re
from typing import Any

from bibliomap.parsers._common import clean, dedupe, map_document_type, normalize_doi
from bibliomap.schema import Author, Record, SourceFormat

_TAG = re.compile(r"<[^>]+>")
_OPENALEX_PREFIX = "https://openalex.org/"

Work = dict[str, Any]


def _short_id(url: str | None) -> str | None:
    return url.removeprefix(_OPENALEX_PREFIX) if url else None


def reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str | None:
    """OpenAlex ships abstracts as word -> positions; rebuild the text."""
    if not inverted:
        return None
    positions = {pos: word for word, places in inverted.items() for pos in places}
    return clean(" ".join(positions[i] for i in sorted(positions)))


def _authors(work: Work) -> list[Author]:
    authors: list[Author] = []
    for authorship in work.get("authorships") or []:
        person = authorship.get("author") or {}
        name = clean(person.get("display_name")) or clean(authorship.get("raw_author_name"))
        if not name:
            continue
        orcid = person.get("orcid")
        affiliations = authorship.get("raw_affiliation_strings") or [
            inst.get("display_name") for inst in authorship.get("institutions") or []
        ]
        authors.append(
            Author(
                name=name,
                full_name=name,
                orcid=orcid.removeprefix("https://orcid.org/") if orcid else None,
                affiliations=[a for a in (clean(x) for x in affiliations) if a],
            )
        )
    return authors


def _institutions(work: Work) -> list[str]:
    """Record-level affiliations use OpenAlex's disambiguated institution names."""
    names = [
        inst.get("display_name")
        for authorship in work.get("authorships") or []
        for inst in authorship.get("institutions") or []
    ]
    return dedupe([n for n in (clean(x) for x in names) if n])


def work_to_record(work: Work) -> Record | None:
    title = clean(_TAG.sub("", work.get("display_name") or work.get("title") or ""))
    if not title:
        return None

    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    biblio = work.get("biblio") or {}
    ids = work.get("ids") or {}
    pmid = ids.get("pmid")

    return Record(
        source_format=SourceFormat.OPENALEX,
        source_id=_short_id(work.get("id")),
        title=title,
        authors=_authors(work),
        year=work.get("publication_year"),
        source_title=clean(source.get("display_name")),
        document_type=map_document_type(work.get("type")),
        document_type_raw=work.get("type"),
        abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
        doi=normalize_doi(work.get("doi")),
        pmid=pmid.rstrip("/").rsplit("/", 1)[-1] if pmid else None,
        issn=list(source.get("issn") or []),
        volume=biblio.get("volume"),
        issue=biblio.get("issue"),
        page_start=biblio.get("first_page"),
        page_end=biblio.get("last_page"),
        language=work.get("language"),
        publisher=clean(source.get("host_organization_name")),
        index_keywords=dedupe(
            [k for k in (clean(kw.get("display_name")) for kw in work.get("keywords") or []) if k]
        ),
        affiliations=_institutions(work),
        cited_by=work.get("cited_by_count"),
        # Cited works as OpenAlex IDs; enables exact citation links later.
        references=[r for r in (_short_id(u) for u in work.get("referenced_works") or []) if r],
        url=location.get("landing_page_url"),
    )
