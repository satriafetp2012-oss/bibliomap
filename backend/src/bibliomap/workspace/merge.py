"""Merge a group of duplicate records into one, keeping provenance."""

from __future__ import annotations

from pydantic import BaseModel

from bibliomap.parsers._common import dedupe
from bibliomap.schema import Record, SourceFormat
from bibliomap.workspace.dedup import StoredRecord

_LIST_FIELDS = ("issn", "author_keywords", "index_keywords", "affiliations", "references")
# Weighted completeness: abstracts and references matter most for analysis.
_WEIGHTS = {"abstract": 3, "references": 3, "doi": 2, "authors": 2, "affiliations": 1}


class SourceRef(BaseModel):
    record_id: int
    import_id: int
    source_format: SourceFormat
    source_id: str | None


class MergedRecord(BaseModel):
    id: int
    record: Record
    sources: list[SourceRef]


def _completeness(record: Record) -> int:
    score = 0
    for name, value in record:
        if value in (None, "", []):
            continue
        score += _WEIGHTS.get(name, 1)
    if any(a.affiliations for a in record.authors):
        score += 1
    return score


def _source_ref(item: StoredRecord) -> SourceRef:
    return SourceRef(
        record_id=item.id,
        import_id=item.import_id,
        source_format=item.record.source_format,
        source_id=item.record.source_id,
    )


def merge_group(items: list[StoredRecord]) -> MergedRecord:
    """Start from the most complete record and fill gaps from the others."""
    ranked = sorted(items, key=lambda i: (-_completeness(i.record), i.id))
    base = ranked[0].record.model_copy(deep=True)
    others = [i.record for i in ranked[1:]]

    for name in Record.model_fields:
        if name in _LIST_FIELDS or name in ("source_format", "authors"):
            continue
        if getattr(base, name) in (None, ""):
            for other in others:
                if (value := getattr(other, name)) not in (None, ""):
                    setattr(base, name, value)
                    break

    if not base.authors:
        base.authors = next((o.authors for o in others if o.authors), [])
    for name in _LIST_FIELDS:
        combined = [v for r in [base, *others] for v in getattr(r, name)]
        setattr(base, name, dedupe(combined))
    counts = [r.cited_by for r in [base, *others] if r.cited_by is not None]
    base.cited_by = max(counts) if counts else None

    return MergedRecord(
        id=min(i.id for i in items),
        record=base,
        sources=[_source_ref(i) for i in sorted(items, key=lambda i: i.id)],
    )


def build_merged(items: list[StoredRecord], groups: list[list[int]]) -> list[MergedRecord]:
    """Collapse duplicate groups; singletons pass through unchanged."""
    by_id = {item.id: item for item in items}
    grouped = {record_id for group in groups for record_id in group}
    merged = [merge_group([by_id[i] for i in group]) for group in groups]
    merged += [
        MergedRecord(id=item.id, record=item.record, sources=[_source_ref(item)])
        for item in items
        if item.id not in grouped
    ]
    return sorted(merged, key=lambda m: m.id)
