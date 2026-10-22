"""Compute a workspace's derived state: dedup -> merge -> filter -> PRISMA.

Results are deterministic for a given workspace version, so they are cached
per (workspace id, version) and recomputed only after a change.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass

from bibliomap.workspace.dedup import DedupOutcome, StoredRecord, find_duplicates
from bibliomap.workspace.filters import FilterOutcome, apply_filters
from bibliomap.workspace.merge import MergedRecord, build_merged
from bibliomap.workspace.prisma import PrismaFlow, SourceCount, build_prisma
from bibliomap.workspace.store import ImportInfo, Workspace, WorkspaceStore

_CACHE_SIZE = 8


@dataclass(frozen=True)
class WorkspaceState:
    workspace: Workspace
    imports: list[ImportInfo]
    records: dict[int, StoredRecord]
    dedup: DedupOutcome
    merged: list[MergedRecord]
    filtered: FilterOutcome
    prisma: PrismaFlow


def _source_counts(imports: list[ImportInfo]) -> list[SourceCount]:
    totals: dict[str, int] = {}
    for imp in imports:
        totals[imp.label] = totals.get(imp.label, 0) + imp.record_count
    return [SourceCount(label=label, count=count) for label, count in totals.items()]


def compute_state(store: WorkspaceStore, workspace_id: str) -> WorkspaceState:
    workspace = store.get_workspace(workspace_id)
    imports = store.list_imports(workspace_id)
    items = store.load_records(workspace_id)
    dedup = find_duplicates(items, store.decisions(workspace_id))
    merged = build_merged(items, dedup.groups)
    filtered = apply_filters(merged, workspace.filters)
    prisma = build_prisma(
        sources=_source_counts(imports),
        duplicates_removed=dedup.duplicates_removed,
        exclusions=filtered.counts(),
        screened=len(filtered.kept),
        pending_duplicate_reviews=len(dedup.pending),
    )
    return WorkspaceState(
        workspace=workspace,
        imports=imports,
        records={item.id: item for item in items},
        dedup=dedup,
        merged=merged,
        filtered=filtered,
        prisma=prisma,
    )


class StateCache:
    """Small LRU of computed states keyed by workspace id and version."""

    def __init__(self, store: WorkspaceStore, size: int = _CACHE_SIZE) -> None:
        self.store = store
        self.size = size
        self._entries: OrderedDict[tuple[str, int], WorkspaceState] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, workspace_id: str) -> WorkspaceState:
        version = self.store.get_workspace(workspace_id).version
        key = (workspace_id, version)
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]
        state = compute_state(self.store, workspace_id)
        with self._lock:
            # Drop stale versions of this workspace before inserting.
            for stale in [k for k in self._entries if k[0] == workspace_id]:
                del self._entries[stale]
            self._entries[(workspace_id, state.workspace.version)] = state
            while len(self._entries) > self.size:
                self._entries.popitem(last=False)
        return state
