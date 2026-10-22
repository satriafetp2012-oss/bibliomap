"""PRISMA 2020 flow counts (new systematic review, databases and registers).

Counts that later phases will fill (screening decisions, full-text
retrieval) are ``None`` so the diagram can show them as not yet available
rather than as zero.
"""

from __future__ import annotations

from pydantic import BaseModel

from bibliomap.workspace.filters import ExclusionReason


class SourceCount(BaseModel):
    label: str
    count: int


class PrismaFlow(BaseModel):
    # Identification
    identified: int
    identified_by_source: list[SourceCount]
    duplicates_removed: int
    automation_ineligible: int
    automation_ineligible_by_reason: dict[ExclusionReason, int]
    other_removed: int = 0
    # Screening
    screened: int
    screening_excluded: int | None = None
    sought_for_retrieval: int | None = None
    not_retrieved: int | None = None
    assessed_for_eligibility: int | None = None
    reports_excluded: int | None = None
    included: int | None = None
    # Review progress: pairs still awaiting a manual duplicate decision.
    pending_duplicate_reviews: int = 0


def build_prisma(
    sources: list[SourceCount],
    duplicates_removed: int,
    exclusions: dict[ExclusionReason, int],
    screened: int,
    pending_duplicate_reviews: int,
) -> PrismaFlow:
    return PrismaFlow(
        identified=sum(s.count for s in sources),
        identified_by_source=sources,
        duplicates_removed=duplicates_removed,
        automation_ineligible=sum(exclusions.values()),
        automation_ineligible_by_reason=exclusions,
        screened=screened,
        pending_duplicate_reviews=pending_duplicate_reviews,
    )
