"""Build the five bibliometric network types.

Edge weights are raw co-occurrence counts; normalization to association
strength (Van Eck & Waltman 2009) happens separately so callers can choose
raw counts, association strength or inclusion (Salton cosine).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from enum import StrEnum
from itertools import combinations

from pydantic import BaseModel

from bibliomap.analysis.entities import (
    EntityIndex,
    EntityKind,
    Thesaurus,
    build_index,
    document_label,
    normalize_key,
)
from bibliomap.schema import Record

#: Reference strings carry volume and page noise; cut them down to
#: "author, year, source" before matching, which is how WoS writes them.
_REFERENCE_PARTS = 3


class NetworkType(StrEnum):
    CO_AUTHORSHIP = "co_authorship"
    CO_OCCURRENCE = "co_occurrence"
    CITATION = "citation"
    BIBLIOGRAPHIC_COUPLING = "bibliographic_coupling"
    CO_CITATION = "co_citation"


class Normalization(StrEnum):
    NONE = "none"
    ASSOCIATION = "association"
    INCLUSION = "inclusion"


class Node(BaseModel):
    id: str
    label: str
    weight: int
    #: Sum of raw link weights; VOSviewer calls this "total link strength".
    link_strength: float = 0.0
    documents: int = 0
    citations: int = 0
    year: float | None = None


class Edge(BaseModel):
    source: str
    target: str
    weight: float
    raw_weight: int


class Network(BaseModel):
    type: NetworkType
    unit: EntityKind
    nodes: list[Node]
    edges: list[Edge]
    normalization: Normalization
    #: Entities that met min_occurrences but ended up with no links.
    isolated: int = 0


def _reference_key(reference: str) -> str:
    parts = [p.strip() for p in reference.split(",")]
    return normalize_key(", ".join(parts[:_REFERENCE_PARTS]))


def _pair_counts(groups: list[list[str]]) -> Counter[tuple[str, str]]:
    """Count co-occurrences of keys appearing in the same group."""
    pairs: Counter[tuple[str, str]] = Counter()
    for keys in groups:
        unique = sorted(set(keys))
        for a, b in combinations(unique, 2):
            pairs[(a, b)] += 1
    return pairs


def _shared_item_counts(items_by_doc: dict[int, set[str]]) -> Counter[tuple[int, int]]:
    """Count shared items between documents using an inverted index.

    Comparing every document pair is quadratic; most pairs share nothing, so
    walk each item's document list instead.
    """
    by_item: dict[str, list[int]] = defaultdict(list)
    for doc_id, items in items_by_doc.items():
        for item in items:
            by_item[item].append(doc_id)

    pairs: Counter[tuple[int, int]] = Counter()
    for doc_ids in by_item.values():
        # An item shared by very many documents links them all; that is
        # genuine but quadratic, so skip the few pathological ones.
        if len(doc_ids) > 500:
            continue
        for a, b in combinations(sorted(doc_ids), 2):
            pairs[(a, b)] += 1
    return pairs


def normalize_edges(
    edges: Counter[tuple[str, str]], weights: dict[str, int], method: Normalization
) -> list[Edge]:
    """Apply association strength or inclusion to raw co-occurrence counts."""
    result: list[Edge] = []
    for (a, b), raw in edges.items():
        match method:
            case Normalization.NONE:
                weight = float(raw)
            case Normalization.ASSOCIATION:
                # c_ij / (w_i * w_j): the ratio of observed to expected
                # co-occurrences if links were random.
                denominator = weights[a] * weights[b]
                weight = raw / denominator if denominator else 0.0
            case Normalization.INCLUSION:
                denominator = (weights[a] * weights[b]) ** 0.5
                weight = raw / denominator if denominator else 0.0
        result.append(Edge(source=a, target=b, weight=weight, raw_weight=raw))
    return result


def _assemble(
    network_type: NetworkType,
    unit: EntityKind,
    labels: dict[str, str],
    node_weights: dict[str, int],
    pairs: Counter[tuple[str, str]],
    normalization: Normalization,
    extras: dict[str, dict[str, float]] | None = None,
) -> Network:
    edges = normalize_edges(pairs, node_weights, normalization)
    strength: dict[str, float] = defaultdict(float)
    for edge in edges:
        strength[edge.source] += edge.raw_weight
        strength[edge.target] += edge.raw_weight

    extras = extras or {}
    nodes = [
        Node(
            id=key,
            label=labels.get(key, key),
            weight=weight,
            link_strength=strength.get(key, 0.0),
            documents=int(extras.get("documents", {}).get(key, weight)),
            citations=int(extras.get("citations", {}).get(key, 0)),
            year=extras.get("year", {}).get(key),
        )
        for key, weight in node_weights.items()
    ]
    nodes.sort(key=lambda n: (-n.weight, n.label))
    return Network(
        type=network_type,
        unit=unit,
        nodes=nodes,
        edges=edges,
        normalization=normalization,
        isolated=sum(1 for n in nodes if n.link_strength == 0),
    )


def _entity_extras(index: EntityIndex, records: dict[int, Record]) -> dict[str, dict[str, float]]:
    citations: dict[str, float] = {}
    years: dict[str, float] = {}
    for key, doc_ids in index.documents.items():
        citations[key] = sum(records[d].cited_by or 0 for d in doc_ids)
        known = [y for d in doc_ids if (y := records[d].year) is not None]
        if known:
            years[key] = round(sum(known) / len(known), 1)
    return {"citations": citations, "year": years}


def co_occurrence_network(
    records: dict[int, Record],
    unit: EntityKind,
    *,
    min_occurrences: int = 2,
    normalization: Normalization = Normalization.ASSOCIATION,
    thesaurus: Thesaurus | None = None,
    network_type: NetworkType = NetworkType.CO_OCCURRENCE,
) -> Network:
    """Co-authorship or keyword co-occurrence, depending on ``unit``."""
    index = build_index(records, unit, thesaurus)
    kept = {k: len(docs) for k, docs in index.documents.items() if len(docs) >= min_occurrences}
    groups = [[k for k in keys if k in kept] for keys in index.by_document.values()]
    return _assemble(
        network_type,
        unit,
        index.labels,
        kept,
        _pair_counts(groups),
        normalization,
        _entity_extras(index, records),
    )


def coupling_network(
    records: dict[int, Record],
    unit: EntityKind,
    *,
    min_shared: int = 2,
    min_occurrences: int = 1,
    normalization: Normalization = Normalization.ASSOCIATION,
) -> Network:
    """Bibliographic coupling: units linked by the references they share."""
    index = build_index(records, unit)
    refs_by_doc = {
        doc_id: {_reference_key(r) for r in record.references if r.strip()}
        for doc_id, record in records.items()
    }

    # Pool references per unit (a unit may span several documents).
    refs_by_unit: dict[str, set[str]] = defaultdict(set)
    for key, doc_ids in index.documents.items():
        for doc_id in doc_ids:
            refs_by_unit[key] |= refs_by_doc.get(doc_id, set())

    kept = {
        k: len(docs)
        for k, docs in index.documents.items()
        if len(docs) >= min_occurrences and refs_by_unit[k]
    }
    unit_ids = {key: i for i, key in enumerate(kept)}
    back = {i: key for key, i in unit_ids.items()}
    shared = _shared_item_counts({unit_ids[k]: refs_by_unit[k] for k in kept})

    pairs: Counter[tuple[str, str]] = Counter()
    for (a, b), count in shared.items():
        if count >= min_shared:
            key_a, key_b = sorted((back[a], back[b]))
            pairs[(key_a, key_b)] = count

    return _assemble(
        NetworkType.BIBLIOGRAPHIC_COUPLING,
        unit,
        index.labels,
        kept,
        pairs,
        normalization,
        _entity_extras(index, records),
    )


def co_citation_network(
    records: dict[int, Record],
    *,
    min_citations: int = 2,
    min_shared: int = 2,
    normalization: Normalization = Normalization.ASSOCIATION,
) -> Network:
    """Co-citation: cited references that appear together in citing papers."""
    labels: dict[str, str] = {}
    cited_by: dict[str, set[int]] = defaultdict(set)
    for doc_id, record in records.items():
        for reference in record.references:
            if not reference.strip():
                continue
            key = _reference_key(reference)
            if not key:
                continue
            cited_by[key].add(doc_id)
            if key not in labels or len(reference) < len(labels[key]):
                labels[key] = reference.strip()

    kept = {k: len(docs) for k, docs in cited_by.items() if len(docs) >= min_citations}
    groups = [[key for key in kept if doc_id in cited_by[key]] for doc_id in records]
    pairs = Counter({p: c for p, c in _pair_counts(groups).items() if c >= min_shared})
    return _assemble(
        NetworkType.CO_CITATION, EntityKind.REFERENCE, labels, kept, pairs, normalization
    )


def citation_network(
    records: dict[int, Record],
    *,
    normalization: Normalization = Normalization.NONE,
) -> Network:
    """Direct citation links between documents in the corpus.

    A document cites another when one of its reference strings matches the
    other's citation key, or its DOI.
    """
    labels = {str(doc_id): document_label(record) for doc_id, record in records.items()}
    by_citation_key: dict[str, str] = {}
    by_doi: dict[str, str] = {}
    for doc_id, record in records.items():
        by_citation_key.setdefault(normalize_key(document_label(record)), str(doc_id))
        if record.doi:
            by_doi.setdefault(record.doi, str(doc_id))

    pairs: Counter[tuple[str, str]] = Counter()
    for doc_id, record in records.items():
        source = str(doc_id)
        for reference in record.references:
            text = reference.strip()
            if not text:
                continue
            target = by_citation_key.get(_reference_key(text))
            if target is None:
                lowered = text.lower()
                target = next(
                    (node for doi, node in by_doi.items() if doi and doi in lowered), None
                )
            if target is not None and target != source:
                pairs[tuple(sorted((source, target)))] += 1  # type: ignore[index]

    weights = {str(doc_id): records[doc_id].cited_by or 0 for doc_id in records}
    extras = {
        "citations": {str(d): float(records[d].cited_by or 0) for d in records},
        "year": {str(d): float(y) for d in records if (y := records[d].year) is not None},
        "documents": {str(d): 1.0 for d in records},
    }
    return _assemble(
        NetworkType.CITATION, EntityKind.DOCUMENT, labels, weights, pairs, normalization, extras
    )
