import type {
  FilterSpec,
  ImportInfo,
  ImportPreview,
  OpenAlexCount,
  OpenAlexImport,
  OpenAlexQuery,
  PendingPage,
  PrismaFlow,
  RecordPage,
  Workspace,
  WorkspaceSummary,
} from "./types";

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

// --- workspace ----------------------------------------------------------

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw await readError(response);
  return (response.status === 204 ? undefined : await response.json()) as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

const ws = (id: string) => `/api/workspaces/${encodeURIComponent(id)}`;

export const workspaceApi = {
  create: (name?: string) => request<Workspace>("/api/workspaces", jsonInit("POST", { name })),
  summary: (id: string) => request<WorkspaceSummary>(ws(id)),
  importFile(id: string, file: File) {
    const body = new FormData();
    body.append("file", file);
    return request<ImportInfo>(`${ws(id)}/imports/file`, { method: "POST", body });
  },
  importOpenAlex: (id: string, query: OpenAlexQuery, apiKey?: string) =>
    request<ImportInfo>(
      `${ws(id)}/imports/openalex`,
      jsonInit("POST", { query, api_key: apiKey || null }),
    ),
  renameImport: (id: string, importId: number, label: string) =>
    request<void>(`${ws(id)}/imports/${importId}`, jsonInit("PATCH", { label })),
  deleteImport: (id: string, importId: number) =>
    request<void>(`${ws(id)}/imports/${importId}`, { method: "DELETE" }),
  pending: (id: string, limit = 1) =>
    request<PendingPage>(`${ws(id)}/dedup/pending?limit=${limit}`),
  decide: (id: string, recordA: number, recordB: number, same: boolean) =>
    request<void>(
      `${ws(id)}/dedup/decisions`,
      jsonInit("POST", { record_a: recordA, record_b: recordB, same }),
    ),
  undoDecision: (id: string, recordA: number, recordB: number) =>
    request<void>(`${ws(id)}/dedup/decisions?record_a=${recordA}&record_b=${recordB}`, {
      method: "DELETE",
    }),
  setFilters: (id: string, spec: FilterSpec) =>
    request<WorkspaceSummary>(`${ws(id)}/filters`, jsonInit("PUT", spec)),
  records: (id: string, status: "kept" | "excluded", limit = 200) =>
    request<RecordPage>(`${ws(id)}/records?status=${status}&limit=${limit}`),
  prisma: (id: string) => request<PrismaFlow>(`${ws(id)}/prisma`),
};
