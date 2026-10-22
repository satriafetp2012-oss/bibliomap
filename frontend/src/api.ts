import type { ImportPreview, OpenAlexCount, OpenAlexImport, OpenAlexQuery } from "./types";

export class ApiError extends Error {}

async function readError(response: Response): Promise<ApiError> {
  // FastAPI puts a human-readable (Indonesian) message in `detail`; validation
  // errors arrive as a list of {msg} objects instead.
  const detail = await response
    .json()
    .then((data: { detail?: unknown }) => {
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail)) {
        return data.detail.map((d: { msg?: string }) => d.msg).join("; ");
      }
      return null;
    })
    .catch(() => null);
  return new ApiError(detail ?? `HTTP ${response.status}`);
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as T;
}

export async function previewImport(file: File): Promise<ImportPreview> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/imports/preview", { method: "POST", body });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as ImportPreview;
}

export function countOpenAlex(query: OpenAlexQuery, apiKey?: string): Promise<OpenAlexCount> {
  return postJson("/api/openalex/count", { query, api_key: apiKey || null });
}

export function importOpenAlex(query: OpenAlexQuery, apiKey?: string): Promise<OpenAlexImport> {
  return postJson("/api/openalex/import", { query, api_key: apiKey || null });
}
