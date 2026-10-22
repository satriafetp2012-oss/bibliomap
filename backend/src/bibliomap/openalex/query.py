"""Structured OpenAlex query, built from the UI's search form.

The query is turned into ``/works`` parameters in one place so the exact URL
can be shown to users and stored with a project for reproducibility.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self
from urllib.parse import urlencode

from pydantic import BaseModel, Field, model_validator

BASE_URL = "https://api.openalex.org"
PER_PAGE = 200  # OpenAlex maximum
MAX_RESULTS = 5000

# Only the fields the mapper reads; smaller responses are faster.
SELECT_FIELDS = (
    "id,doi,display_name,publication_year,type,language,authorships,primary_location,"
    "biblio,ids,keywords,abstract_inverted_index,cited_by_count,referenced_works"
)

# Commas separate filters and pipes mean OR inside a filter value.
_FILTER_UNSAFE = re.compile(r"[,|]")


class SearchScope(StrEnum):
    TITLE_ABSTRACT = "title_and_abstract"
    TITLE = "title"
    FULLTEXT = "fulltext"


class WorkType(StrEnum):
    ARTICLE = "article"
    REVIEW = "review"
    CONFERENCE_PAPER = "conference-paper"
    BOOK_CHAPTER = "book-chapter"
    BOOK = "book"
    PREPRINT = "preprint"
    LETTER = "letter"
    EDITORIAL = "editorial"


class OpenAlexQuery(BaseModel):
    terms: str = Field(
        min_length=1,
        max_length=500,
        description="Kata kunci; mendukung AND, OR, NOT, tanda kutip, dan kurung.",
    )
    scope: SearchScope = SearchScope.TITLE_ABSTRACT
    year_from: int | None = Field(default=None, ge=1500, le=2100)
    year_to: int | None = Field(default=None, ge=1500, le=2100)
    types: list[WorkType] = Field(default_factory=list)
    languages: list[str] = Field(
        default_factory=list, description="Kode ISO 639-1, mis. 'en', 'id'."
    )
    open_access_only: bool = False
    max_results: int = Field(default=1000, ge=1, le=MAX_RESULTS)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("Tahun awal tidak boleh melebihi tahun akhir.")
        for code in self.languages:
            if not re.fullmatch(r"[a-z]{2}", code):
                raise ValueError(f"Kode bahasa tidak valid: {code!r}.")
        return self


def build_params(query: OpenAlexQuery) -> dict[str, str]:
    """Translate a query into /works parameters (without paging or credentials)."""
    params: dict[str, str] = {}
    filters: list[str] = []

    terms = " ".join(query.terms.split())
    if query.scope is SearchScope.FULLTEXT:
        params["search"] = terms
    else:
        filters.append(f"{query.scope.value}.search:{_FILTER_UNSAFE.sub(' ', terms)}")

    if query.year_from and query.year_to:
        filters.append(f"publication_year:{query.year_from}-{query.year_to}")
    elif query.year_from:
        filters.append(f"publication_year:>{query.year_from - 1}")
    elif query.year_to:
        filters.append(f"publication_year:<{query.year_to + 1}")
    if query.types:
        filters.append("type:" + "|".join(t.value for t in query.types))
    if query.languages:
        filters.append("language:" + "|".join(query.languages))
    if query.open_access_only:
        filters.append("open_access.is_oa:true")

    if filters:
        params["filter"] = ",".join(filters)
    return params


def public_url(query: OpenAlexQuery) -> str:
    """Human-readable query URL, safe to display (never includes an API key)."""
    return f"{BASE_URL}/works?{urlencode(build_params(query), safe=':,|<>')}"
