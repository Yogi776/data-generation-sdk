// Single typed API client. No raw fetch in components.
// Base URL is same-origin by default (FastAPI serves the UI and the API);
// override with NEXT_PUBLIC_API_BASE for local dev against a separate backend.

import type {
  DocsResult,
  GenerateRequest,
  GenerateResult,
  Health,
  ProfileResult,
  QualityReport,
  ScanResult,
  SearchResult,
  SemanticResult,
  Source,
  SqlResult,
  TableDetail,
  TableSummary,
} from "./types";

const BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const { json, headers, ...rest } = init ?? {};
  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(headers ?? {}),
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/health"),

  sources: () => request<Source[]>("/sources"),

  tables: () => request<TableSummary[]>("/metadata/tables"),

  table: (name: string) =>
    request<TableDetail>(`/metadata/tables/${encodeURIComponent(name)}`),

  search: (q: string, limit = 20) =>
    request<SearchResult[]>(
      `/metadata/search?q=${encodeURIComponent(q)}&limit=${limit}`
    ),

  scan: () => request<ScanResult[]>("/scan", { method: "POST", json: {} }),

  profile: (source?: string | null, sampleRows = 10_000) =>
    request<ProfileResult[]>("/profile/run", {
      method: "POST",
      json: { source: source ?? null, sample_rows: sampleRows },
    }),

  generate: (req: GenerateRequest) =>
    request<GenerateResult>("/generate-data", { method: "POST", json: req }),

  semantic: (name = "default", format?: string | null) =>
    request<SemanticResult>("/semantic-model", {
      method: "POST",
      json: { name, format: format ?? null },
    }),

  quality: () =>
    request<QualityReport>("/quality-check", { method: "POST", json: {} }),

  sql: (question: string) =>
    request<SqlResult>("/sql", { method: "POST", json: { question } }),

  docs: () =>
    request<DocsResult>("/docs/generate", { method: "POST", json: {} }),
};
