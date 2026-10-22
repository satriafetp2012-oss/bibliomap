import type { ImportPreview } from "./types";

export class ApiError extends Error {}

export async function previewImport(file: File): Promise<ImportPreview> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/imports/preview", { method: "POST", body });
  if (!response.ok) {
    // FastAPI puts a human-readable (Indonesian) message in `detail`.
    const detail = await response
      .json()
      .then((data: { detail?: unknown }) => (typeof data.detail === "string" ? data.detail : null))
      .catch(() => null);
    throw new ApiError(detail ?? `HTTP ${response.status}`);
  }
  return (await response.json()) as ImportPreview;
}
