"""Canonical bibliographic record schema.

Every parser converts its source format into ``Record`` so that downstream
steps (deduplication, statistics, networks) never deal with source quirks.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SourceFormat(StrEnum):
    """Input formats understood by the importer."""

    WOS = "wos"
    SCOPUS = "scopus"
    RIS = "ris"
    PUBMED = "pubmed"
    BIBTEX = "bibtex"
    OPENALEX = "openalex"
    LENS = "lens"


class DocumentType(StrEnum):
    """Normalized document types shared across databases."""

    ARTICLE = "article"
    REVIEW = "review"
    CONFERENCE_PAPER = "conference_paper"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    EDITORIAL = "editorial"
    LETTER = "letter"
    PREPRINT = "preprint"
    OTHER = "other"


class Author(BaseModel):
    """One author as written in the source, plus optional enrichments."""

    name: str = Field(description="Short form as exported, e.g. 'Smith, J'.")
    full_name: str | None = Field(default=None, description="e.g. 'Smith, John'.")
    orcid: str | None = None
    affiliations: list[str] = Field(default_factory=list)


class Record(BaseModel):
    """A single bibliographic record in canonical form."""

    source_format: SourceFormat
    source_id: str | None = Field(
        default=None, description="WoS UT, Scopus EID, PMID, RIS AN, OpenAlex or Lens ID."
    )
    title: str
    authors: list[Author] = Field(default_factory=list)
    year: int | None = None
    source_title: str | None = Field(default=None, description="Journal, proceedings or book.")
    source_abbrev: str | None = None
    document_type: DocumentType = DocumentType.OTHER
    document_type_raw: str | None = None
    abstract: str | None = None
    doi: str | None = None
    pmid: str | None = None
    issn: list[str] = Field(default_factory=list)
    volume: str | None = None
    issue: str | None = None
    page_start: str | None = None
    page_end: str | None = None
    article_number: str | None = None
    language: str | None = None
    publisher: str | None = None
    author_keywords: list[str] = Field(default_factory=list)
    index_keywords: list[str] = Field(
        default_factory=list, description="Keywords Plus, Scopus index terms or MeSH."
    )
    affiliations: list[str] = Field(default_factory=list)
    cited_by: int | None = None
    references: list[str] = Field(default_factory=list, description="Raw cited-reference strings.")
    url: str | None = None


class ParseWarning(BaseModel):
    """A non-fatal problem found while parsing; the record may be skipped."""

    record_index: int | None = Field(default=None, description="0-based position in the file.")
    message: str


class ParseResult(BaseModel):
    """Output of one parser run."""

    source_format: SourceFormat
    records: list[Record]
    warnings: list[ParseWarning] = Field(default_factory=list)
