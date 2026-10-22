import { describe, expect, it } from "vitest";

import { DEFAULT_IMAGE, mapToSvg } from "./mapImage";
import type { MapNode, ScienceMap } from "./types";

function node(id: string, label: string, over: Partial<MapNode> = {}): MapNode {
  return {
    id,
    label,
    x: 0,
    y: 0,
    cluster: 1,
    weight: 10,
    link_strength: 5,
    documents: 10,
    citations: 2,
    year: 2021,
    ...over,
  };
}

const map: ScienceMap = {
  type: "co_occurrence",
  unit: "keyword",
  normalization: "association",
  nodes: [
    node("a", "helmet & safety", { x: -1, y: -1, weight: 20 }),
    node("b", "<motorcycle>", { x: 1, y: 1, weight: 5, cluster: 2 }),
    node("c", "injury", { x: 0, y: 1, weight: 1, cluster: 3 }),
  ],
  edges: [{ source: "a", target: "b", weight: 0.5, raw_weight: 4 }],
  clusters: 3,
  modularity: 0.4,
  iterations: 200,
  truncated_from: null,
  edges_before_limit: null,
};

describe("mapToSvg", () => {
  it("produces valid SVG sized to the options", () => {
    const svg = mapToSvg(map);
    const doc = new DOMParser().parseFromString(svg, "image/svg+xml");

    expect(doc.querySelector("parsererror")).toBeNull();
    const root = doc.documentElement;
    expect(root.getAttribute("width")).toBe(String(DEFAULT_IMAGE.width));
    expect(doc.querySelectorAll("circle")).toHaveLength(3);
    expect(doc.querySelectorAll("line")).toHaveLength(1);
  });

  it("escapes label text rather than breaking the document", () => {
    const doc = new DOMParser().parseFromString(mapToSvg(map), "image/svg+xml");
    const labels = [...doc.querySelectorAll("text")].map((t) => t.textContent);

    expect(labels).toContain("helmet & safety");
    expect(labels).toContain("<motorcycle>");
  });

  it("colours nodes by cluster and sizes them by weight", () => {
    const doc = new DOMParser().parseFromString(mapToSvg(map), "image/svg+xml");
    const circles = [...doc.querySelectorAll("circle")];
    const fills = circles.map((c) => c.getAttribute("fill"));

    expect(new Set(fills).size).toBe(3);
    const radii = circles.map((c) => Number(c.getAttribute("r")));
    // Node "a" has the largest weight, "c" the smallest.
    expect(radii[0]).toBeGreaterThan(radii[2]);
  });

  it("flips the y axis so the picture matches the screen", () => {
    const doc = new DOMParser().parseFromString(mapToSvg(map), "image/svg+xml");
    const [a, b] = [...doc.querySelectorAll("circle")].map((c) => Number(c.getAttribute("cy")));
    // a is at y=-1 and b at y=+1, so a must be drawn lower down.
    expect(a).toBeGreaterThan(b);
  });

  it("labels only the biggest nodes when the limit is small", () => {
    const doc = new DOMParser().parseFromString(
      mapToSvg(map, { ...DEFAULT_IMAGE, labelLimit: 1 }),
      "image/svg+xml",
    );
    const labels = [...doc.querySelectorAll("text")].map((t) => t.textContent);
    expect(labels).toEqual(["helmet & safety"]);
  });

  it("handles a map whose nodes all sit at one point", () => {
    const flat: ScienceMap = { ...map, nodes: map.nodes.map((n) => ({ ...n, x: 0, y: 0 })) };
    const doc = new DOMParser().parseFromString(mapToSvg(flat), "image/svg+xml");

    expect(doc.querySelector("parsererror")).toBeNull();
    const cx = [...doc.querySelectorAll("circle")].map((c) => Number(c.getAttribute("cx")));
    expect(cx.every(Number.isFinite)).toBe(true);
  });
});
