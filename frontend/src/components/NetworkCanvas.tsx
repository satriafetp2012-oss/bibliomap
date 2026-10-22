import Graph from "graphology";
import { useEffect, useRef } from "react";
import Sigma from "sigma";

import { clusterColor } from "../clusterColors";
import type { MapNode, ScienceMap } from "../types";

/** Node radius in pixels, shrunk as the map gets crowded: 24px circles are
 *  right for 50 items and merge into a solid block at 700. */
function sizeRange(count: number): [number, number] {
  const max = Math.min(24, Math.max(5, 260 / Math.sqrt(Math.max(count, 1))));
  return [Math.max(1.2, max / 7), max];
}
const DIMMED = "rgba(170,170,170,0.22)";

interface Props {
  map: ScienceMap;
  showLabels: boolean;
  highlight: string | null;
  onSelect: (node: MapNode | null) => void;
}

/** Spreading a six-figure array into Math.max overflows the call stack. */
function extent(values: number[]): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const value of values) {
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return values.length ? [min, max] : [0, 1];
}

function buildGraph(map: ScienceMap): Graph {
  const graph = new Graph({ type: "undirected" });
  const [rawMin, rawMax] = extent(map.nodes.map((n) => n.weight));
  const minWeight = Math.min(rawMin, 0);
  const span = Math.max(rawMax - minWeight, 1);
  const [minSize, maxSize] = sizeRange(map.nodes.length);

  for (const node of map.nodes) {
    // Area, not radius, scales with weight so big nodes do not swamp the map.
    const fraction = (node.weight - minWeight) / span;
    graph.addNode(node.id, {
      x: node.x,
      y: node.y,
      size: minSize + Math.sqrt(fraction) * (maxSize - minSize),
      label: node.label,
      color: clusterColor(node.cluster),
    });
  }

  const maxEdge = Math.max(extent(map.edges.map((e) => e.weight))[1], Number.EPSILON);
  for (const edge of map.edges) {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      graph.addEdge(edge.source, edge.target, {
        size: 0.15 + (edge.weight / maxEdge) * 1.2,
        color: "rgba(140,140,140,0.35)",
      });
    }
  }
  return graph;
}

export function NetworkCanvas({ map, showLabels, highlight, onSelect }: Props) {
  const [, maxSize] = sizeRange(map.nodes.length);
  const container = useRef<HTMLDivElement>(null);
  const sigma = useRef<Sigma | null>(null);
  const byId = useRef(new Map<string, MapNode>());
  // Sigma v4 fixes reducers at construction, so the reducer reads this ref
  // and we refresh when the search term changes.
  const query = useRef<string | null>(highlight);
  query.current = highlight;

  useEffect(() => {
    byId.current = new Map(map.nodes.map((n) => [n.id, n]));
    if (!container.current) return;

    const renderer = new Sigma(buildGraph(map), container.current, {
      settings: {
        // Sizes are pixel radii on screen, not layout units: without this
        // sigma scales them with the camera and large maps turn into blobs.
        itemSizesReference: "screen",
        zoomToSizeRatioFunction: (ratio: number) => ratio,
        renderLabels: showLabels,
        labelDensity: 0.6,
        labelGridCellSize: 120,
        // Relative to the node sizes, so labels still appear on dense maps.
        labelRenderedSizeThreshold: maxSize * 0.45,
        // Dragging a very large map stays smooth without edges.
        hideEdgesOnMove: map.nodes.length > 2000,
      },
      nodeReducer: (_key, data) => {
        const term = query.current;
        if (!term) return data;
        const label = typeof data.label === "string" ? data.label : "";
        return label.toLowerCase().includes(term.toLowerCase())
          ? { ...data, forceLabel: true }
          : { ...data, color: DIMMED, label: "" };
      },
    });
    sigma.current = renderer;

    renderer.on("clickNode", ({ node }) => onSelect(byId.current.get(node) ?? null));
    renderer.on("clickStage", () => onSelect(null));

    return () => {
      renderer.kill();
      sigma.current = null;
    };
  }, [map, onSelect, showLabels, maxSize]);

  useEffect(() => {
    sigma.current?.setSetting("renderLabels", showLabels);
  }, [showLabels]);

  useEffect(() => {
    sigma.current?.refresh();
  }, [highlight]);

  return <div ref={container} className="network-canvas" />;
}
