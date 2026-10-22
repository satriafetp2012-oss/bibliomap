/** Cluster palette, shared by the canvas, the SVG export and the legend.
 *
 * Kept free of renderer imports so it can be used where WebGL is absent.
 */
export const CLUSTER_COLORS = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#65a30d",
];

export const clusterColor = (cluster: number): string =>
  CLUSTER_COLORS[(cluster - 1) % CLUSTER_COLORS.length];
