"""Leiden clustering and VOS layout.

Clustering uses leidenalg with the RB configuration model, i.e. modularity
with a resolution parameter: at ``resolution=1`` it is standard modularity,
and raising it yields smaller clusters. Unlike CPM, its scale does not
depend on whether edge weights are raw counts or association strengths.

The layout implements the VOS (visualization of similarities) technique of
Van Eck & Waltman: minimize the weighted sum of squared distances between
related items subject to their mean distance being 1. The implementation
here is written from the published objective function, using a
majorization step (SMACOF-style) followed by the normalizations the method
prescribes. It is not derived from VOSviewer's own source.

    E(x) = sum_ij s_ij * |x_i - x_j|^2,  subject to
    (2 / n(n-1)) * sum_ij |x_i - x_j| = 1
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import igraph as ig
import leidenalg as la
import numpy as np

from bibliomap.analysis.networks import Network

_EPSILON = 1e-9
#: Random but fixed: runs with the same input must give the same map.
DEFAULT_SEED = 42
#: Memory ceiling for one block of the repulsion computation (~64 MB).
_BLOCK_BYTES = 64 * 1024 * 1024
#: Rough budget of node-pair updates per layout, so small maps iterate more
#: without large maps taking minutes. Pairwise distances are stable well
#: before the bound: at 250 iterations they correlate 0.996 with a 4,000
#: iteration run on a real 258-node co-authorship map.
_PAIR_BUDGET = 6_000_000_000
_MIN_ITERATIONS = 200
#: Largest move one node may make in one iteration, as a share of the map's
#: current radius.
_STEP_FRACTION = 0.1
#: Outliers are drawn no further out than this multiple of the 95th
#: percentile radius.
_RIM_MULTIPLE = 2.0
_MAX_ITERATIONS = 1000


def iteration_budget(size: int) -> int:
    """Iterations to run for a map of ``size`` nodes."""
    if size < 2:
        return 0
    budget = _PAIR_BUDGET // (size * size)
    return int(max(_MIN_ITERATIONS, min(_MAX_ITERATIONS, budget)))


@dataclass(frozen=True)
class LayoutResult:
    positions: dict[str, tuple[float, float]]
    clusters: dict[str, int]
    modularity: float
    iterations: int


def _graph(network: Network) -> tuple[ig.Graph, list[str]]:
    ids = [node.id for node in network.nodes]
    position = {node_id: i for i, node_id in enumerate(ids)}
    edges = [(position[e.source], position[e.target]) for e in network.edges]
    weights = [max(e.weight, _EPSILON) for e in network.edges]
    graph = ig.Graph(n=len(ids), edges=edges, directed=False)
    graph.es["weight"] = weights
    return graph, ids


def cluster(
    network: Network, resolution: float = 1.0, seed: int = DEFAULT_SEED, min_size: int = 1
) -> tuple[dict[str, int], float]:
    """Leiden clustering with CPM; returns cluster per node and modularity.

    Clusters smaller than ``min_size`` are merged into the nearest larger
    cluster, matching VOSviewer's "minimum cluster size" option.
    """
    graph, ids = _graph(network)
    if graph.vcount() == 0:
        return {}, 0.0
    if graph.ecount() == 0:
        return {node_id: 0 for node_id in ids}, 0.0

    partition = la.find_partition(
        graph,
        la.RBConfigurationVertexPartition,
        weights=graph.es["weight"],
        resolution_parameter=resolution,
        seed=seed,
        n_iterations=-1,  # run until the partition stops improving
    )
    membership = list(partition.membership)
    if min_size > 1:
        membership = _merge_small(graph, membership, min_size)

    # Renumber so cluster 1 is the largest; VOSviewer numbers from 1.
    sizes: dict[int, int] = {}
    for c in membership:
        sizes[c] = sizes.get(c, 0) + 1
    order = {
        old: new
        for new, (old, _) in enumerate(
            sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0])), start=1
        )
    }
    clusters = {ids[i]: order[c] for i, c in enumerate(membership)}
    modularity = graph.modularity(membership, weights=graph.es["weight"])
    return clusters, round(float(modularity), 4)


def _merge_small(graph: ig.Graph, membership: list[int], min_size: int) -> list[int]:
    sizes: dict[int, int] = {}
    for c in membership:
        sizes[c] = sizes.get(c, 0) + 1
    small = {c for c, size in sizes.items() if size < min_size}
    if not small or len(small) == len(sizes):
        return membership

    result = list(membership)
    for vertex in range(graph.vcount()):
        if result[vertex] not in small:
            continue
        # Move to the neighbouring cluster this node is most strongly tied to.
        best, best_weight = None, 0.0
        for neighbour in graph.neighbors(vertex):
            cluster_id = membership[neighbour]
            if cluster_id in small:
                continue
            edge = graph.get_eid(vertex, neighbour, error=False)
            weight = float(graph.es[edge]["weight"]) if edge >= 0 else 0.0
            if weight > best_weight:
                best, best_weight = cluster_id, weight
        if best is not None:
            result[vertex] = best
    return result


def _similarity_matrix(network: Network, ids: list[str]) -> np.ndarray:
    position = {node_id: i for i, node_id in enumerate(ids)}
    size = len(ids)
    matrix = np.zeros((size, size), dtype=np.float64)
    for edge in network.edges:
        i, j = position[edge.source], position[edge.target]
        matrix[i, j] = matrix[j, i] = max(edge.weight, 0.0)
    return matrix


def _radius(points: np.ndarray) -> float:
    return float(np.sqrt((points**2).sum(axis=1)).max()) if len(points) else 0.0


def _typical_radius(points: np.ndarray) -> float:
    """Median distance from the origin: a scale one stray node cannot inflate."""
    return float(np.median(np.sqrt((points**2).sum(axis=1)))) if len(points) else 0.0


def _components(similarity: np.ndarray) -> list[np.ndarray]:
    """Index groups of mutually reachable nodes, largest first."""
    size = len(similarity)
    seen = np.zeros(size, dtype=bool)
    groups: list[np.ndarray] = []
    neighbours = [np.flatnonzero(row) for row in similarity > 0]
    for start in range(size):
        if seen[start]:
            continue
        stack, members = [start], []
        seen[start] = True
        while stack:
            current = stack.pop()
            members.append(current)
            for other in neighbours[current]:
                if not seen[other]:
                    seen[other] = True
                    stack.append(int(other))
        groups.append(np.array(sorted(members)))
    groups.sort(key=len, reverse=True)
    return groups


def _place_component(
    similarity: np.ndarray, steps: int, tolerance: float, seed: int
) -> tuple[np.ndarray, int]:
    """Run the VOS iteration on one connected component."""
    size = len(similarity)
    if size == 1:
        return np.zeros((1, 2)), 0

    rng = np.random.default_rng(seed)
    points = rng.normal(scale=0.1, size=(size, 2))
    degree = similarity.sum(axis=1)
    # Repulsion strength: with attraction summing to the total similarity,
    # this keeps the two terms comparable so clusters separate without
    # exploding.
    repulsion = similarity.sum() / (size * (size - 1))
    denominator = np.maximum(degree, _EPSILON)[:, None]
    iteration = 0

    for step in range(1, steps + 1):
        iteration = step
        # Attraction: weighted centroid of each node's neighbours.
        attraction = similarity @ points
        push = _repulsion(points, repulsion)
        delta = (attraction + push) / denominator - points

        # Degrees span orders of magnitude under association strength, so a
        # weakly linked node can take an enormous step and never come back.
        # Capping the move per iteration keeps the dynamics stable without
        # moving where the iteration settles.
        limit = _STEP_FRACTION * (_typical_radius(points) + 1.0)
        lengths = np.sqrt((delta**2).sum(axis=1))
        scale = np.minimum(1.0, limit / np.maximum(lengths, _EPSILON))
        points = points + delta * scale[:, None]

        if float(lengths.max()) < tolerance:
            break

    return _normalize(points, degree), iteration


def vos_layout(
    network: Network,
    *,
    iterations: int | None = None,
    tolerance: float = 1e-5,
    seed: int = DEFAULT_SEED,
) -> tuple[dict[str, tuple[float, float]], int]:
    """Place nodes with the VOS technique.

    Minimizes sum_ij s_ij |x_i - x_j|^2 against a repulsion term, then
    rescales so the mean distance is 1.

    Each connected component is laid out on its own and the components are
    then packed around the largest. Nothing attracts separate components to
    each other, so laying them out together lets repulsion drive them apart
    for as long as the iteration runs: a three-author group once landed 24
    map units away, which flattened everything else into a dot.
    """
    ids = [node.id for node in network.nodes]
    if not ids:
        return {}, 0
    if len(ids) == 1:
        return {ids[0]: (0.0, 0.0)}, 0

    similarity = _similarity_matrix(network, ids)
    groups = _components(similarity)
    steps = iteration_budget(len(ids)) if iterations is None else iterations

    placements: list[tuple[np.ndarray, np.ndarray]] = []
    used_iterations = 0
    for index, members in enumerate(groups):
        block = similarity[np.ix_(members, members)]
        # Each component gets its own seed, so adding one does not reshuffle
        # the others.
        points, iteration = _place_component(block, steps, tolerance, seed + index)
        used_iterations = max(used_iterations, iteration)
        placements.append((members, points))

    offsets = _pack(placements)

    placed: dict[str, tuple[float, float]] = {}
    for (members, points), offset in zip(placements, offsets, strict=True):
        shifted = points + offset
        for row, node_index in enumerate(members):
            placed[ids[node_index]] = (
                round(float(shifted[row, 0]), 4),
                round(float(shifted[row, 1]), 4),
            )
    return placed, used_iterations


def _extent(points: np.ndarray) -> tuple[float, float]:
    """Width and height of a component's bounding box."""
    if not len(points):
        return 0.0, 0.0
    return (
        float(points[:, 0].max() - points[:, 0].min()),
        float(points[:, 1].max() - points[:, 1].min()),
    )


def _pack(placements: list[tuple[np.ndarray, np.ndarray]]) -> list[np.ndarray]:
    """Offsets that put the largest component at the centre and lay the rest
    out in rows beneath it.

    Shelf packing rather than a ring: a ring has to clear the widest
    component in every direction, so a handful of three-author groups would
    push the frame out until the main map was a sliver in the middle.
    """
    offsets = [np.zeros(2)]
    if len(placements) == 1:
        return offsets

    main_width, main_height = _extent(placements[0][1])
    # The map is normalized to a mean pairwise distance of 1, so the gap has
    # to exceed that: otherwise two small components sit closer to each other
    # than each one's own members do.
    gap = 1.5
    # Keep rows about as wide as the main component so the whole map stays
    # roughly square.
    row_limit = max(main_width, 1.0)

    cursor_x = 0.0
    row_top = -main_height / 2 - gap
    row_height = 0.0

    for _, points in placements[1:]:
        width, height = _extent(points)
        if cursor_x > 0 and cursor_x + width > row_limit:
            # Start a new row under the previous one.
            row_top -= row_height + gap
            cursor_x, row_height = 0.0, 0.0
        centre_x = -row_limit / 2 + cursor_x + width / 2
        centre_y = row_top - height / 2
        # points are centred on their own origin, so the offset is the centre.
        offsets.append(np.array([centre_x, centre_y]))
        cursor_x += width + gap
        row_height = max(row_height, height)

    return offsets


def _ring(ids: list[str], radius: float) -> dict[str, tuple[float, float]]:
    """Evenly spaced points on a circle, for items with nothing to attract them."""
    if not ids:
        return {}
    angles = np.linspace(0, 2 * math.pi, len(ids), endpoint=False)
    return {
        node_id: (round(float(radius * np.cos(a)), 4), round(float(radius * np.sin(a)), 4))
        for node_id, a in zip(ids, angles, strict=True)
    }


def _repulsion(points: np.ndarray, strength: float) -> np.ndarray:
    """Sum of strength * (x_i - x_j) / d_ij over all j, for every i.

    Written as two matrix products rather than an (n, n, 2) difference
    tensor, which at 5,000 nodes would need hundreds of megabytes:

        sum_j (x_i - x_j)/d_ij = x_i * sum_j 1/d_ij - sum_j x_j/d_ij

    Rows are processed in blocks so peak memory stays bounded.
    """
    size = len(points)
    push = np.empty_like(points)
    squared = (points**2).sum(axis=1)
    block = max(1, min(size, _BLOCK_BYTES // (8 * max(size, 1))))

    for start in range(0, size, block):
        stop = min(start + block, size)
        chunk = points[start:stop]
        # Squared distances without forming the difference tensor.
        sq = squared[start:stop, None] + squared[None, :] - 2.0 * (chunk @ points.T)
        np.maximum(sq, 0.0, out=sq)
        inverse = 1.0 / np.sqrt(sq + _EPSILON)
        # A node does not push itself.
        inverse[np.arange(start, stop) - start, np.arange(start, stop)] = 0.0
        push[start:stop] = chunk * inverse.sum(axis=1)[:, None] - inverse @ points

    push *= strength
    return push


def _normalize(points: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Centre at the weighted origin, rotate to principal axes, scale.

    The VOS method fixes translation, rotation and scale this way so that
    two maps of the same data always come out in the same orientation.
    """
    total = weights.sum()
    centre = (points * weights[:, None]).sum(axis=0) / total if total > 0 else points.mean(axis=0)
    centred = points - centre

    covariance = (centred * weights[:, None]).T @ centred / max(total, _EPSILON)
    _, vectors = np.linalg.eigh(covariance)
    # eigh returns ascending eigenvalues; put the largest variance on x.
    rotated = centred @ vectors[:, ::-1]

    # Flip so the layout is reproducible rather than mirrored at random.
    for axis in range(2):
        if np.sum(rotated[:, axis] ** 3) < 0:
            rotated[:, axis] *= -1

    size = len(points)
    if size > 1:
        differences = rotated[:, None, :] - rotated[None, :, :]
        distances = np.sqrt((differences**2).sum(axis=-1))
        mean_distance = distances.sum() / (size * (size - 1))
        if mean_distance > _EPSILON:
            rotated /= mean_distance
    return _draw_outliers_to_rim(rotated)


def _draw_outliers_to_rim(points: np.ndarray) -> np.ndarray:
    """Pull far outliers in to the edge of the map, keeping their direction.

    An item with almost no similarity to anything has its true optimum
    hundreds of units out: the objective function balances a vanishing
    attraction against repulsion from every other item. Drawn literally,
    one such node squeezes the rest of the map into a dot. Placing it on
    the rim keeps it visible, and at the periphery, where it belongs.
    """
    if len(points) < 3:
        return points
    radii = np.sqrt((points**2).sum(axis=1))
    rim = float(np.percentile(radii, 95)) * _RIM_MULTIPLE
    if rim <= _EPSILON:
        return points
    beyond = radii > rim
    if not beyond.any():
        return points
    scale = np.ones_like(radii)
    scale[beyond] = rim / radii[beyond]
    return points * scale[:, None]


def build_layout(
    network: Network,
    *,
    resolution: float = 1.0,
    min_cluster_size: int = 1,
    seed: int = DEFAULT_SEED,
    iterations: int | None = None,
) -> LayoutResult:
    clusters, modularity = cluster(network, resolution, seed, min_cluster_size)
    positions, used = vos_layout(network, iterations=iterations, seed=seed)
    return LayoutResult(
        positions=positions, clusters=clusters, modularity=modularity, iterations=used
    )
