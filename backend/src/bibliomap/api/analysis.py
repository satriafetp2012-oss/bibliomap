"""Statistics and science-mapping endpoints for a workspace.

Networks are computed from the filtered, deduplicated records, so what a
user maps is exactly what their PRISMA flow reports as screened.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from bibliomap.analysis.entities import EntityKind
from bibliomap.analysis.layout import build_layout
from bibliomap.analysis.metrics import (
    BradfordAnalysis,
    LotkaFit,
    Overview,
    RankedEntity,
    bradford,
    lotka,
    overview,
    rank_entities,
)
from bibliomap.analysis.networks import (
    Edge,
    Network,
    NetworkType,
    Normalization,
    citation_network,
    co_citation_network,
    co_occurrence_network,
    coupling_network,
)
from bibliomap.api.workspaces import Cache, get_state
from bibliomap.schema import Record

router = APIRouter(prefix="/api/workspaces/{workspace_id}/analysis", tags=["analysis"])

_CACHE_SIZE = 6
#: Units each network type can be built on.
NETWORK_UNITS: dict[NetworkType, tuple[EntityKind, ...]] = {
    NetworkType.CO_AUTHORSHIP: (EntityKind.AUTHOR, EntityKind.AFFILIATION, EntityKind.COUNTRY),
    NetworkType.CO_OCCURRENCE: (EntityKind.KEYWORD, EntityKind.INDEX_KEYWORD),
    NetworkType.CITATION: (EntityKind.DOCUMENT,),
    NetworkType.BIBLIOGRAPHIC_COUPLING: (
        EntityKind.DOCUMENT,
        EntityKind.SOURCE,
        EntityKind.AUTHOR,
        EntityKind.AFFILIATION,
        EntityKind.COUNTRY,
    ),
    NetworkType.CO_CITATION: (EntityKind.REFERENCE,),
}


class Statistics(BaseModel):
    overview: Overview
    top_sources: list[RankedEntity]
    top_authors: list[RankedEntity]
    top_affiliations: list[RankedEntity]
    top_countries: list[RankedEntity]
    top_keywords: list[RankedEntity]
    lotka: LotkaFit
    bradford: BradfordAnalysis


class MapNode(BaseModel):
    id: str
    label: str
    x: float
    y: float
    cluster: int
    weight: int
    link_strength: float
    documents: int
    citations: int
    year: float | None


class ScienceMap(BaseModel):
    type: NetworkType
    unit: EntityKind
    normalization: Normalization
    nodes: list[MapNode]
    edges: list[Edge]
    clusters: int
    modularity: float
    iterations: int
    truncated_from: int | None = Field(
        default=None, description="Jumlah node sebelum dibatasi max_nodes."
    )
    edges_before_limit: int | None = Field(
        default=None, description="Jumlah tautan sebelum dibatasi max_edges."
    )


class NetworkOptions(BaseModel):
    """Everything that changes a map; also its cache key."""

    type: NetworkType = NetworkType.CO_OCCURRENCE
    unit: EntityKind = EntityKind.KEYWORD
    min_occurrences: int = 2
    min_shared: int = 2
    normalization: Normalization = Normalization.ASSOCIATION
    resolution: float = 1.0
    min_cluster_size: int = 1
    max_nodes: int = 1000
    #: Dense maps have far more links than a screen can show; VOSviewer caps
    #: the drawn lines the same way. Clustering and layout still use them all.
    max_edges: int = 2000

    def key(self) -> tuple[object, ...]:
        return tuple(self.model_dump().values())


@dataclass
class _Entry:
    statistics: Statistics | None = None
    maps: dict[tuple[object, ...], ScienceMap] | None = None


class AnalysisCache:
    """Per workspace version; analysis is deterministic, so it is reusable."""

    def __init__(self, size: int = _CACHE_SIZE) -> None:
        self._entries: OrderedDict[tuple[str, int], _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def entry(self, workspace_id: str, version: int) -> _Entry:
        key = (workspace_id, version)
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key]
            for stale in [k for k in self._entries if k[0] == workspace_id]:
                del self._entries[stale]
            entry = _Entry()
            self._entries[key] = entry
            while len(self._entries) > _CACHE_SIZE:
                self._entries.popitem(last=False)
            return entry


_cache = AnalysisCache()


def _records(cache: Cache, workspace_id: str) -> tuple[dict[int, Record], int]:
    state = get_state(cache, workspace_id)
    records = {item.id: item.record for item in state.filtered.kept}
    return records, state.workspace.version


def compute_statistics(records: dict[int, Record], limit: int = 20) -> Statistics:
    return Statistics(
        overview=overview(records),
        top_sources=rank_entities(records, EntityKind.SOURCE, limit),
        top_authors=rank_entities(records, EntityKind.AUTHOR, limit),
        top_affiliations=rank_entities(records, EntityKind.AFFILIATION, limit),
        top_countries=rank_entities(records, EntityKind.COUNTRY, limit),
        top_keywords=rank_entities(records, EntityKind.KEYWORD, limit),
        lotka=lotka(records),
        bradford=bradford(records),
    )


def build_network(records: dict[int, Record], options: NetworkOptions) -> Network:
    match options.type:
        case NetworkType.CO_AUTHORSHIP | NetworkType.CO_OCCURRENCE:
            return co_occurrence_network(
                records,
                options.unit,
                min_occurrences=options.min_occurrences,
                normalization=options.normalization,
                network_type=options.type,
            )
        case NetworkType.BIBLIOGRAPHIC_COUPLING:
            return coupling_network(
                records,
                options.unit,
                min_shared=options.min_shared,
                min_occurrences=options.min_occurrences,
                normalization=options.normalization,
            )
        case NetworkType.CO_CITATION:
            return co_citation_network(
                records,
                min_citations=options.min_occurrences,
                min_shared=options.min_shared,
                normalization=options.normalization,
            )
        case NetworkType.CITATION:
            return citation_network(records, normalization=options.normalization)


def _truncate(network: Network, max_nodes: int) -> tuple[Network, int | None]:
    """Keep the strongest nodes so a browser can still render the map."""
    if len(network.nodes) <= max_nodes:
        return network, None
    original = len(network.nodes)
    kept = sorted(network.nodes, key=lambda n: (-n.weight, -n.link_strength))[:max_nodes]
    keep_ids = {n.id for n in kept}
    edges = [e for e in network.edges if e.source in keep_ids and e.target in keep_ids]
    return network.model_copy(update={"nodes": kept, "edges": edges}), original


def _strongest_edges(edges: list[Edge], limit: int) -> tuple[list[Edge], int | None]:
    """Strongest links only; a dense map is an unreadable block otherwise."""
    if len(edges) <= limit:
        return edges, None
    strongest = sorted(edges, key=lambda e: (-e.weight, -e.raw_weight))[:limit]
    return strongest, len(edges)


def compute_map(records: dict[int, Record], options: NetworkOptions) -> ScienceMap:
    network, original = _truncate(build_network(records, options), options.max_nodes)
    # Cluster and lay out on the complete network, then thin the lines.
    layout = build_layout(
        network, resolution=options.resolution, min_cluster_size=options.min_cluster_size
    )
    edges, edges_before = _strongest_edges(network.edges, options.max_edges)
    nodes = [
        MapNode(
            id=node.id,
            label=node.label,
            x=layout.positions.get(node.id, (0.0, 0.0))[0],
            y=layout.positions.get(node.id, (0.0, 0.0))[1],
            cluster=layout.clusters.get(node.id, 1),
            weight=node.weight,
            link_strength=round(node.link_strength, 4),
            documents=node.documents,
            citations=node.citations,
            year=node.year,
        )
        for node in network.nodes
    ]
    return ScienceMap(
        type=network.type,
        unit=network.unit,
        normalization=network.normalization,
        nodes=nodes,
        edges=edges,
        clusters=len({n.cluster for n in nodes}),
        modularity=layout.modularity,
        iterations=layout.iterations,
        truncated_from=original,
        edges_before_limit=edges_before,
    )


@router.get("/statistics")
async def statistics(
    workspace_id: str, cache: Cache, limit: Annotated[int, Query(ge=5, le=100)] = 20
) -> Statistics:
    records, version = _records(cache, workspace_id)
    entry = _cache.entry(workspace_id, version)
    if entry.statistics is None or limit != 20:
        result = await run_in_threadpool(compute_statistics, records, limit)
        if limit == 20:
            entry.statistics = result
        return result
    return entry.statistics


@router.get("/network-units")
def network_units() -> dict[NetworkType, list[EntityKind]]:
    """Which units each network type supports, for the UI's dropdowns."""
    return {network: list(units) for network, units in NETWORK_UNITS.items()}


@router.post("/map")
async def science_map(workspace_id: str, options: NetworkOptions, cache: Cache) -> ScienceMap:
    records, version = _records(cache, workspace_id)
    entry = _cache.entry(workspace_id, version)
    if entry.maps is None:
        entry.maps = {}
    key = options.key()
    if (cached := entry.maps.get(key)) is not None:
        return cached
    # Building and laying out a large map takes seconds; keep the loop free.
    result = await run_in_threadpool(compute_map, records, options)
    entry.maps[key] = result
    return result
