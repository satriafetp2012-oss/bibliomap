/** Render a map to PNG or SVG for publication.
 *
 * Both are drawn from the map data rather than captured from the canvas, so
 * the output is independent of the current zoom, device pixel ratio and
 * viewport size. SVG stays editable in Illustrator or Inkscape.
 */
import type { MapNode, ScienceMap } from "./types";
import { clusterColor } from "./clusterColors";

export interface ImageOptions {
  width: number;
  height: number;
  /** Draw the label of a node only if it is among the biggest. */
  labelLimit: number;
  background: string;
  edgeOpacity: number;
}

export const DEFAULT_IMAGE: ImageOptions = {
  width: 2000,
  height: 1500,
  labelLimit: 120,
  background: "#ffffff",
  edgeOpacity: 0.25,
};

const MARGIN = 0.06;
const MIN_RADIUS = 3;
const MAX_RADIUS = 40;

interface Projected {
  node: MapNode;
  cx: number;
  cy: number;
  r: number;
  label: boolean;
}

function project(map: ScienceMap, options: ImageOptions): Projected[] {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let maxWeight = 1;
  for (const n of map.nodes) {
    if (n.x < minX) minX = n.x;
    if (n.x > maxX) maxX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.y > maxY) maxY = n.y;
    if (n.weight > maxWeight) maxWeight = n.weight;
  }
  const spanX = Math.max(maxX - minX, 1e-6);
  const spanY = Math.max(maxY - minY, 1e-6);
  // One scale for both axes so the map is not stretched.
  const scale = Math.min(
    (options.width * (1 - 2 * MARGIN)) / spanX,
    (options.height * (1 - 2 * MARGIN)) / spanY,
  );
  const offsetX = (options.width - spanX * scale) / 2;
  const offsetY = (options.height - spanY * scale) / 2;

  const labelled = new Set(
    [...map.nodes]
      .sort((a, b) => b.weight - a.weight || b.link_strength - a.link_strength)
      .slice(0, options.labelLimit)
      .map((n) => n.id),
  );
  const radius = Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, 900 / Math.sqrt(map.nodes.length)));

  return map.nodes.map((node) => ({
    node,
    cx: offsetX + (node.x - minX) * scale,
    // SVG and canvas y grows downwards; flip so the map matches the screen.
    cy: offsetY + (maxY - node.y) * scale,
    r: MIN_RADIUS + Math.sqrt(node.weight / maxWeight) * (radius - MIN_RADIUS),
    label: labelled.has(node.id),
  }));
}

function escapeXml(value: string): string {
  return value.replace(
    /[<>&"']/g,
    (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;" })[c]!,
  );
}

export function mapToSvg(map: ScienceMap, options: ImageOptions = DEFAULT_IMAGE): string {
  const points = project(map, options);
  const byId = new Map(points.map((p) => [p.node.id, p]));
  let maxEdge = Number.EPSILON;
  for (const e of map.edges) if (e.weight > maxEdge) maxEdge = e.weight;

  const edges = map.edges
    .map((edge) => {
      const a = byId.get(edge.source);
      const b = byId.get(edge.target);
      if (!a || !b) return "";
      const width = (0.3 + (edge.weight / maxEdge) * 2).toFixed(2);
      return `<line x1="${a.cx.toFixed(1)}" y1="${a.cy.toFixed(1)}" x2="${b.cx.toFixed(1)}" y2="${b.cy.toFixed(1)}" stroke-width="${width}"/>`;
    })
    .join("");

  const circles = points
    .map(
      (p) =>
        `<circle cx="${p.cx.toFixed(1)}" cy="${p.cy.toFixed(1)}" r="${p.r.toFixed(1)}" fill="${clusterColor(p.node.cluster)}" fill-opacity="0.85"/>`,
    )
    .join("");

  const labels = points
    .filter((p) => p.label)
    .map((p) => {
      const size = Math.max(10, p.r * 0.9);
      const y = (p.cy + p.r + size).toFixed(1);
      return `<text x="${p.cx.toFixed(1)}" y="${y}" font-size="${size.toFixed(1)}">${escapeXml(p.node.label)}</text>`;
    })
    .join("");

  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<svg xmlns="http://www.w3.org/2000/svg" width="${options.width}" height="${options.height}" viewBox="0 0 ${options.width} ${options.height}">`,
    `<rect width="100%" height="100%" fill="${options.background}"/>`,
    `<g stroke="#808080" stroke-opacity="${options.edgeOpacity}">${edges}</g>`,
    `<g>${circles}</g>`,
    `<g font-family="Helvetica, Arial, sans-serif" fill="#111111" text-anchor="middle">${labels}</g>`,
    `</svg>`,
  ].join("\n");
}

export async function mapToPng(
  map: ScienceMap,
  options: ImageOptions = DEFAULT_IMAGE,
): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = options.width;
  canvas.height = options.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas unavailable");

  ctx.fillStyle = options.background;
  ctx.fillRect(0, 0, options.width, options.height);

  const points = project(map, options);
  const byId = new Map(points.map((p) => [p.node.id, p]));
  let maxEdge = Number.EPSILON;
  for (const e of map.edges) if (e.weight > maxEdge) maxEdge = e.weight;

  ctx.strokeStyle = `rgba(128,128,128,${options.edgeOpacity})`;
  for (const edge of map.edges) {
    const a = byId.get(edge.source);
    const b = byId.get(edge.target);
    if (!a || !b) continue;
    ctx.lineWidth = 0.3 + (edge.weight / maxEdge) * 2;
    ctx.beginPath();
    ctx.moveTo(a.cx, a.cy);
    ctx.lineTo(b.cx, b.cy);
    ctx.stroke();
  }

  ctx.globalAlpha = 0.85;
  for (const p of points) {
    ctx.fillStyle = clusterColor(p.node.cluster);
    ctx.beginPath();
    ctx.arc(p.cx, p.cy, p.r, 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.globalAlpha = 1;
  ctx.fillStyle = "#111111";
  ctx.textAlign = "center";
  for (const p of points) {
    if (!p.label) continue;
    const size = Math.max(10, p.r * 0.9);
    ctx.font = `${size}px Helvetica, Arial, sans-serif`;
    ctx.fillText(p.node.label, p.cx, p.cy + p.r + size);
  }

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("PNG encoding failed"))),
      "image/png",
    );
  });
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
