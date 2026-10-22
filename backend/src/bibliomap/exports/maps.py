"""Export a computed map to formats other tools read.

The VOSviewer map/network pair follows the layout of the example files
shipped with VOSviewer: a tab-separated map file with ``id``, ``label``,
``x``, ``y``, ``cluster`` and ``weight<...>``/``score<...>`` columns, and a
sparse network file of ``id1 id2 strength`` rows. Only the file format is
reproduced, so a Bibliomap map opens in VOSviewer unchanged.
"""

from __future__ import annotations

import csv
import io
from xml.etree import ElementTree as ET

from bibliomap.api.analysis import MapNode, ScienceMap

# VOSviewer reads these as UTF-8 and expects a BOM, as its own files have.
BOM = "\ufeff"


def _numbered(map_: ScienceMap) -> dict[str, int]:
    """VOSviewer needs consecutive integer ids starting at 1."""
    return {node.id: i for i, node in enumerate(map_.nodes, start=1)}


def _rows(map_: ScienceMap) -> list[list[object]]:
    numbers = _numbered(map_)
    return [
        [
            numbers[n.id],
            n.label,
            n.x,
            n.y,
            n.cluster,
            n.documents,
            round(n.link_strength, 4),
            n.citations,
            n.year if n.year is not None else "",
        ]
        for n in map_.nodes
    ]


def vosviewer_map(map_: ScienceMap) -> str:
    header = [
        "id",
        "label",
        "x",
        "y",
        "cluster",
        "weight<Documents>",
        "weight<Total link strength>",
        "weight<Citations>",
        "score<Avg. pub. year>",
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(header)
    writer.writerows(_rows(map_))
    return BOM + buffer.getvalue()


def vosviewer_network(map_: ScienceMap) -> str:
    numbers = _numbered(map_)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    for edge in map_.edges:
        writer.writerow([numbers[edge.source], numbers[edge.target], round(edge.weight, 6)])
    return BOM + buffer.getvalue()


def nodes_csv(map_: ScienceMap) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["id", "label", "cluster", "x", "y", "documents", "link_strength", "citations", "year"]
    )
    for n in map_.nodes:
        writer.writerow(
            [
                n.id,
                n.label,
                n.cluster,
                n.x,
                n.y,
                n.documents,
                round(n.link_strength, 4),
                n.citations,
                n.year if n.year is not None else "",
            ]
        )
    return buffer.getvalue()


def edges_csv(map_: ScienceMap) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["source", "target", "weight", "raw_weight"])
    labels = {n.id: n.label for n in map_.nodes}
    for edge in map_.edges:
        writer.writerow(
            [
                labels.get(edge.source, edge.source),
                labels.get(edge.target, edge.target),
                round(edge.weight, 6),
                edge.raw_weight,
            ]
        )
    return buffer.getvalue()


def pajek_network(map_: ScienceMap) -> str:
    """Pajek .net, read by Gephi, Pajek and VOSviewer."""
    numbers = _numbered(map_)
    lines = [f"*Vertices {len(map_.nodes)}"]
    for node in map_.nodes:
        # Pajek quotes labels and takes coordinates in the unit square.
        label = node.label.replace('"', "'")
        lines.append(f'{numbers[node.id]} "{label}"')
    lines.append("*Edges")
    for edge in map_.edges:
        lines.append(f"{numbers[edge.source]} {numbers[edge.target]} {round(edge.weight, 6)}")
    return "\n".join(lines) + "\n"


def pajek_clusters(map_: ScienceMap) -> str:
    """Pajek .clu partition file, in the same vertex order as the .net."""
    lines = [f"*Vertices {len(map_.nodes)}"]
    lines.extend(str(node.cluster) for node in map_.nodes)
    return "\n".join(lines) + "\n"


def graphml(map_: ScienceMap) -> str:
    """GraphML with node attributes, for Gephi and Cytoscape."""
    ns = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}graphml")

    attributes: list[tuple[str, str, str, str]] = [
        ("label", "node", "label", "string"),
        ("cluster", "node", "cluster", "int"),
        ("x", "node", "x", "double"),
        ("y", "node", "y", "double"),
        ("documents", "node", "documents", "int"),
        ("citations", "node", "citations", "int"),
        ("linkstrength", "node", "link_strength", "double"),
        ("weight", "edge", "weight", "double"),
    ]
    for key_id, domain, name, kind in attributes:
        key = ET.SubElement(root, f"{{{ns}}}key")
        key.set("id", key_id)
        key.set("for", domain)
        key.set("attr.name", name)
        key.set("attr.type", kind)

    graph = ET.SubElement(root, f"{{{ns}}}graph")
    graph.set("edgedefault", "undirected")

    def data(parent: ET.Element, key_id: str, value: object) -> None:
        element = ET.SubElement(parent, f"{{{ns}}}data")
        element.set("key", key_id)
        element.text = str(value)

    for node in map_.nodes:
        element = ET.SubElement(graph, f"{{{ns}}}node")
        element.set("id", node.id)
        data(element, "label", node.label)
        data(element, "cluster", node.cluster)
        data(element, "x", node.x)
        data(element, "y", node.y)
        data(element, "documents", node.documents)
        data(element, "citations", node.citations)
        data(element, "linkstrength", round(node.link_strength, 4))

    for index, edge in enumerate(map_.edges):
        element = ET.SubElement(graph, f"{{{ns}}}edge")
        element.set("id", f"e{index}")
        element.set("source", edge.source)
        element.set("target", edge.target)
        data(element, "weight", round(edge.weight, 6))

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


#: Hues matching the cluster colours the web map uses.
CLUSTER_COLORS = [
    (37, 99, 235),
    (220, 38, 38),
    (22, 163, 74),
    (217, 119, 6),
    (124, 58, 237),
    (8, 145, 178),
    (219, 39, 119),
    (101, 163, 13),
]


def cluster_colors(map_: ScienceMap) -> str:
    """VOSviewer cluster_colors.txt, so a reopened map keeps its palette."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["cluster", "red", "green", "blue"])
    for cluster in range(1, map_.clusters + 1):
        red, green, blue = CLUSTER_COLORS[(cluster - 1) % len(CLUSTER_COLORS)]
        writer.writerow([cluster, red, green, blue])
    return BOM + buffer.getvalue()


def top_nodes(map_: ScienceMap, limit: int) -> list[MapNode]:
    return sorted(map_.nodes, key=lambda n: (-n.weight, -n.link_strength))[:limit]
