"""Automatic eligibility filters applied after deduplication.

Records removed here are reported in PRISMA as "marked as ineligible by
automation tools", broken down by the first rule each record failed.
"""

from __future__ import annotations

from collections import Counter
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from bibliomap.parsers._common import normalize_language
from bibliomap.schema import DocumentType
from bibliomap.workspace.merge import MergedRecord


class ExclusionReason(StrEnum):
    YEAR = "year"
    DOCUMENT_TYPE = "document_type"
    LANGUAGE = "language"
    CITATIONS = "citations"
    NO_ABSTRACT = "no_abstract"


class FilterSpec(BaseModel):
    year_from: int | None = Field(default=None, ge=1500, le=2100)
    year_to: int | None = Field(default=None, ge=1500, le=2100)
    document_types: list[DocumentType] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list, description="ISO 639-1, mis. 'en'.")
    min_cited_by: int | None = Field(default=None, ge=0)
    require_abstract: bool = False

    @model_validator(mode="after")
    def _check(self) -> FilterSpec:
        if self.year_from and self.year_to and self.year_from > self.year_to:
            raise ValueError("Tahun awal tidak boleh melebihi tahun akhir.")
        self.languages = [code.strip().lower() for code in self.languages if code.strip()]
        return self


class FilterOutcome(BaseModel):
    kept: list[MergedRecord]
    excluded: list[tuple[MergedRecord, ExclusionReason]]

    def counts(self) -> dict[ExclusionReason, int]:
        return dict(Counter(reason for _, reason in self.excluded))


def exclusion_reason(item: MergedRecord, spec: FilterSpec) -> ExclusionReason | None:
    """First rule the record fails, or None if it passes every filter."""
    rec = item.record
    # A record with an unknown value is kept: filters must not silently drop
    # studies just because a database left a field empty.
    if rec.year is not None and (
        (spec.year_from and rec.year < spec.year_from) or (spec.year_to and rec.year > spec.year_to)
    ):
        return ExclusionReason.YEAR
    if spec.document_types and rec.document_type not in spec.document_types:
        return ExclusionReason.DOCUMENT_TYPE
    language = normalize_language(rec.language)
    if spec.languages and language is not None and language not in spec.languages:
        return ExclusionReason.LANGUAGE
    if (
        spec.min_cited_by is not None
        and rec.cited_by is not None
        and rec.cited_by < spec.min_cited_by
    ):
        return ExclusionReason.CITATIONS
    if spec.require_abstract and not rec.abstract:
        return ExclusionReason.NO_ABSTRACT
    return None


def apply_filters(items: list[MergedRecord], spec: FilterSpec) -> FilterOutcome:
    kept: list[MergedRecord] = []
    excluded: list[tuple[MergedRecord, ExclusionReason]] = []
    for item in items:
        reason = exclusion_reason(item, spec)
        if reason is None:
            kept.append(item)
        else:
            excluded.append((item, reason))
    return FilterOutcome(kept=kept, excluded=excluded)
