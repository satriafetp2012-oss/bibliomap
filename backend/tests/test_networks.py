import math

import pytest

from bibliomap.analysis.entities import EntityKind
from bibliomap.analysis.layout import build_layout, cluster, vos_layout
from bibliomap.analysis.networks import (
    NetworkType,
    Normalization,
    citation_network,
    co_citation_network,
    co_occurrence_network,
    coupling_network,
)
from bibliomap.schema import Author, Record, SourceFormat


def rec(**fields) -> Record:
    fields.setdefault("title", "T")
    return Record(source_format=SourceFormat.WOS, **fields)


def authors(*names: str) -> list[Author]:
    return [Author(name=n) for n in names]


@pytest.fixture
def collab() -> dict[int, Record]:
    # Two teams linked by one bridging author (Dewi).
    return {
        1: rec(authors=authors("Santoso, B", "Lee, M"), year=2020, cited_by=10),
        2: rec(authors=authors("Santoso, B", "Lee, M", "Dewi, S"), year=2021, cited_by=5),
        3: rec(authors=authors("Dewi, S", "Putra, R"), year=2021, cited_by=2),
        4: rec(authors=authors("Putra, R", "Sari, N"), year=2022, cited_by=0),
        5: rec(authors=authors("Putra, R", "Sari, N"), year=2022, cited_by=1),
    }


def test_co_authorship_network(collab):
    net = co_occurrence_network(
        collab,
        EntityKind.AUTHOR,
        min_occurrences=2,
        normalization=Normalization.NONE,
        network_type=NetworkType.CO_AUTHORSHIP,
    )

    assert net.type is NetworkType.CO_AUTHORSHIP
    assert {n.label for n in net.nodes} == {
        "Santoso, B",
        "Lee, M",
        "Dewi, S",
        "Putra, R",
        "Sari, N",
    }
    weights = {(e.source, e.target): e.raw_weight for e in net.edges}
    assert weights[("lee m", "santoso b")] == 2  # co-authored twice
    assert weights[("putra r", "sari n")] == 2
    assert ("dewi s", "putra r") in weights
    top = next(n for n in net.nodes if n.label == "Putra, R")
    assert top.weight == 3 and top.citations == 3 and top.year == pytest.approx(2021.7, abs=0.1)


def test_min_occurrences_filters_nodes(collab):
    net = co_occurrence_network(collab, EntityKind.AUTHOR, min_occurrences=3)
    assert {n.label for n in net.nodes} == {"Putra, R"}
    assert net.edges == []
    assert net.isolated == 1


def test_association_strength_normalization():
    # A and B always appear together; C appears often but shares little.
    records = {
        i: rec(author_keywords=["a", "b"] + (["c"] if i % 5 == 0 else [])) for i in range(1, 21)
    }
    net = co_occurrence_network(
        records, EntityKind.KEYWORD, min_occurrences=2, normalization=Normalization.ASSOCIATION
    )
    weights = {tuple(sorted((e.source, e.target))): e.weight for e in net.edges}
    # a-b: 20 / (20*20) = 0.05 ; a-c: 4 / (20*4) = 0.05 -> equally associated
    assert weights[("a", "b")] == pytest.approx(0.05)
    assert weights[("a", "c")] == pytest.approx(0.05)
    raw = {tuple(sorted((e.source, e.target))): e.raw_weight for e in net.edges}
    assert raw[("a", "b")] == 20 and raw[("a", "c")] == 4


def test_inclusion_normalization_is_cosine():
    records = {
        1: rec(author_keywords=["x", "y"]),
        2: rec(author_keywords=["x", "y"]),
        3: rec(author_keywords=["x"]),
    }
    net = co_occurrence_network(
        records, EntityKind.KEYWORD, min_occurrences=2, normalization=Normalization.INCLUSION
    )
    # x occurs 3 times, y twice, together twice: 2 / sqrt(3*2)
    assert net.edges[0].weight == pytest.approx(2 / (6**0.5))


def test_bibliographic_coupling():
    records = {
        1: rec(
            authors=authors("A, A"), references=["Peden M, 2004, WORLD REPORT", "WHO, 2018, STATUS"]
        ),
        2: rec(
            authors=authors("B, B"),
            references=["Peden M, 2004, WORLD REPORT, V1, P2", "WHO, 2018, STATUS"],
        ),
        3: rec(authors=authors("C, C"), references=["Other X, 1999, SOMETHING"]),
    }
    net = coupling_network(
        records, EntityKind.DOCUMENT, min_shared=2, normalization=Normalization.NONE
    )

    assert net.type is NetworkType.BIBLIOGRAPHIC_COUPLING
    assert len(net.edges) == 1
    # Volume and page noise is stripped, so the two references match.
    assert net.edges[0].raw_weight == 2


def test_co_citation_network():
    shared = ["Peden M, 2004, WORLD REPORT", "WHO, 2018, GLOBAL STATUS"]
    records = {
        1: rec(references=shared),
        2: rec(references=shared),
        3: rec(references=["Peden M, 2004, WORLD REPORT", "Lonely Z, 1990, NOWHERE"]),
    }
    net = co_citation_network(
        records, min_citations=2, min_shared=2, normalization=Normalization.NONE
    )

    assert net.type is NetworkType.CO_CITATION
    assert {n.label for n in net.nodes} == {
        "Peden M, 2004, WORLD REPORT",
        "WHO, 2018, GLOBAL STATUS",
    }
    assert net.edges[0].raw_weight == 2


def test_citation_network_links_documents_by_reference_and_doi():
    records = {
        1: rec(authors=authors("Santoso, B"), year=2020, source_abbrev="Inj Prev", doi="10.1/a"),
        2: rec(
            authors=authors("Lee, M"), year=2022, references=["Santoso B, 2020, Inj Prev, V1, P1"]
        ),
        3: rec(
            authors=authors("Wu, X"),
            year=2023,
            references=["see https://doi.org/10.1/a for details"],
        ),
    }
    net = citation_network(records)

    links = {tuple(sorted((e.source, e.target))) for e in net.edges}
    assert ("1", "2") in links
    assert ("1", "3") in links


# --- clustering and layout ------------------------------------------------


@pytest.fixture
def two_cliques():
    # Two groups of 4, joined by a single weak link.
    records = {}
    doc = 0
    for group in (["a1", "a2", "a3", "a4"], ["b1", "b2", "b3", "b4"]):
        for i, x in enumerate(group):
            for y in group[i + 1 :]:
                doc += 1
                records[doc] = rec(author_keywords=[x, y])
    doc += 1
    records[doc] = rec(author_keywords=["a1", "b1"])
    return co_occurrence_network(
        records, EntityKind.KEYWORD, min_occurrences=1, normalization=Normalization.NONE
    )


def test_cluster_finds_two_groups(two_cliques):
    clusters, modularity = cluster(two_cliques, resolution=1.0)

    groups = {}
    for key, cluster_id in clusters.items():
        groups.setdefault(cluster_id, set()).add(key)
    assert len(groups) == 2
    assert {frozenset(g) for g in groups.values()} == {
        frozenset({"a1", "a2", "a3", "a4"}),
        frozenset({"b1", "b2", "b3", "b4"}),
    }
    assert modularity > 0.3
    # Cluster 1 is the largest and numbering starts at 1.
    assert min(clusters.values()) == 1


def test_clustering_is_deterministic(two_cliques):
    assert cluster(two_cliques, seed=7)[0] == cluster(two_cliques, seed=7)[0]


def test_min_cluster_size_merges_small_clusters():
    records = {
        1: rec(author_keywords=["a", "b"]),
        2: rec(author_keywords=["a", "b"]),
        3: rec(author_keywords=["c", "d"]),
    }
    net = co_occurrence_network(
        records, EntityKind.KEYWORD, min_occurrences=1, normalization=Normalization.NONE
    )
    assert len(set(cluster(net, min_size=1)[0].values())) == 2
    assert len(set(cluster(net, min_size=3)[0].values())) <= 2


def test_vos_layout_separates_clusters(two_cliques):
    positions, iterations = vos_layout(two_cliques)

    assert len(positions) == 8
    assert iterations > 0

    def spread(keys):
        pts = [positions[k] for k in keys]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        return (cx, cy), max(math.dist(p, (cx, cy)) for p in pts)

    centre_a, radius_a = spread(["a1", "a2", "a3", "a4"])
    centre_b, radius_b = spread(["b1", "b2", "b3", "b4"])
    # The two groups sit further apart than either group is wide.
    assert math.dist(centre_a, centre_b) > max(radius_a, radius_b)


def test_layout_is_deterministic_and_normalized(two_cliques):
    first, _ = vos_layout(two_cliques, seed=3)
    second, _ = vos_layout(two_cliques, seed=3)
    assert first == second

    points = list(first.values())
    pairs = [math.dist(p, q) for i, p in enumerate(points) for q in points[i + 1 :]]
    assert sum(pairs) / len(pairs) == pytest.approx(1.0, abs=0.05)
    cx = sum(p[0] for p in points) / len(points)
    assert abs(cx) < 0.5


def test_layout_handles_edge_cases():
    empty = co_occurrence_network({}, EntityKind.KEYWORD)
    assert vos_layout(empty) == ({}, 0)

    single = co_occurrence_network(
        {1: rec(author_keywords=["solo"])}, EntityKind.KEYWORD, min_occurrences=1
    )
    positions, _ = vos_layout(single)
    assert positions == {"solo": (0.0, 0.0)}

    # Nodes with no links at all are placed on a circle, not stacked.
    records = {i: rec(author_keywords=[f"k{i}"]) for i in range(4)}
    isolated = co_occurrence_network(records, EntityKind.KEYWORD, min_occurrences=1)
    positions, _ = vos_layout(isolated)
    assert len(set(positions.values())) == 4


def test_build_layout_returns_clusters_and_positions(two_cliques):
    result = build_layout(two_cliques, resolution=1.0)
    assert set(result.positions) == set(result.clusters)
    assert result.modularity > 0.3


def test_isolated_node_does_not_collapse_the_map():
    """A node with no links divided by a zero degree once threw the whole
    map to the origin; it must sit outside the cluster instead."""
    records = {
        1: rec(author_keywords=["a", "b", "c"]),
        2: rec(author_keywords=["a", "b", "c"]),
        3: rec(author_keywords=["a", "b", "d"]),
        4: rec(author_keywords=["c", "d"]),
        5: rec(author_keywords=["lonely"]),
        6: rec(author_keywords=["lonely"]),
    }
    net = co_occurrence_network(
        records, EntityKind.KEYWORD, min_occurrences=2, normalization=Normalization.ASSOCIATION
    )
    assert net.isolated == 1

    positions, _ = vos_layout(net)

    assert len(positions) == len(net.nodes)
    assert all(all(math.isfinite(v) for v in p) for p in positions.values())
    at_origin = sum(1 for p in positions.values() if p == (0.0, 0.0))
    assert at_origin <= 1
    # The stray sits outside everything that is linked.
    linked = [positions[k] for k in ("a", "b", "c", "d")]
    centre = (
        sum(p[0] for p in linked) / len(linked),
        sum(p[1] for p in linked) / len(linked),
    )
    cluster_radius = max(math.dist(centre, p) for p in linked)
    assert math.dist(centre, positions["lonely"]) > cluster_radius


def test_all_isolated_nodes_are_spread_on_a_circle():
    records = {i: rec(author_keywords=[f"k{i}"]) for i in range(1, 5)}
    records |= {i + 10: rec(author_keywords=[f"k{i}"]) for i in range(1, 5)}
    net = co_occurrence_network(records, EntityKind.KEYWORD, min_occurrences=2)
    assert net.edges == []

    positions, _ = vos_layout(net)
    assert len(set(positions.values())) == 4


def test_disconnected_components_stay_near_each_other():
    """Nothing attracts separate components, so laying them out together
    let repulsion drive them apart for as long as the iteration ran."""
    records = {
        1: rec(author_keywords=["a", "b"]),
        2: rec(author_keywords=["a", "b"]),
        3: rec(author_keywords=["a", "b"]),
        4: rec(author_keywords=["x", "y"]),
        5: rec(author_keywords=["x", "y"]),
        6: rec(author_keywords=["x", "y"]),
    }
    net = co_occurrence_network(records, EntityKind.KEYWORD, min_occurrences=2)
    positions, _ = vos_layout(net)

    radii = [math.dist((0, 0), p) for p in positions.values()]
    assert max(radii) < 5
    # The two pairs stay together.
    assert math.dist(positions["a"], positions["b"]) < math.dist(positions["a"], positions["x"])


def test_a_barely_linked_node_does_not_squash_the_map():
    """One node whose only link is to a hub has its true optimum hundreds
    of units out; it belongs on the rim, not off the map."""
    records: dict[int, Record] = {}
    core = ["c1", "c2", "c3", "c4", "c5"]
    for i, a in enumerate(core):
        for b in core[i + 1 :]:
            records[len(records) + 1] = rec(author_keywords=[a, b])
    # "fringe" appears often but shares a document with the core only once.
    for _ in range(40):
        records[len(records) + 1] = rec(author_keywords=["fringe", "filler"])
    records[len(records) + 1] = rec(author_keywords=["fringe", "c1"])

    net = co_occurrence_network(
        records, EntityKind.KEYWORD, min_occurrences=2, normalization=Normalization.ASSOCIATION
    )
    positions, _ = vos_layout(net)
    radii = {k: math.dist((0, 0), p) for k, p in positions.items()}

    assert all(math.isfinite(r) for r in radii.values())
    # Bounded: before the rim rule this node sat hundreds of units out.
    assert max(radii.values()) < 5
    # The core still holds together, with the fringe outside it.
    assert max(radii[k] for k in core) < min(radii["fringe"], radii["filler"])
