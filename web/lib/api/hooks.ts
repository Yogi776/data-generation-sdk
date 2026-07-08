"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "./client";
import type { GenerateRequest } from "./types";

export const qk = {
  health: ["health"] as const,
  sources: ["sources"] as const,
  tables: ["tables"] as const,
  table: (name: string) => ["table", name] as const,
  search: (q: string) => ["search", q] as const,
};

function errMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Something went wrong";
}

// ---- queries ----
export function useHealth() {
  return useQuery({ queryKey: qk.health, queryFn: api.health, retry: 1 });
}

export function useSources() {
  return useQuery({ queryKey: qk.sources, queryFn: api.sources });
}

export function useTables() {
  return useQuery({ queryKey: qk.tables, queryFn: api.tables });
}

export function useTable(name: string | null) {
  return useQuery({
    queryKey: qk.table(name ?? ""),
    queryFn: () => api.table(name as string),
    enabled: !!name,
  });
}

export function useSearch(q: string) {
  return useQuery({
    queryKey: qk.search(q),
    queryFn: () => api.search(q),
    enabled: q.trim().length > 0,
  });
}

// ---- mutations ----
export function useScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.scan,
    onSuccess: (res) => {
      const total = res.reduce((n, r) => n + (r.tables ?? 0), 0);
      toast.success(`Scan complete — ${total} table(s) across ${res.length} source(s)`);
      qc.invalidateQueries({ queryKey: qk.tables });
      qc.invalidateQueries({ queryKey: qk.sources });
    },
    onError: (e) => toast.error(errMessage(e)),
  });
}

export function useProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { source?: string | null; sampleRows?: number }) =>
      api.profile(v.source, v.sampleRows),
    onSuccess: (res) => {
      toast.success(`Profiled ${res.length} table(s)`);
      qc.invalidateQueries({ queryKey: qk.tables });
    },
    onError: (e) => toast.error(errMessage(e)),
  });
}

export function useGenerate() {
  return useMutation({
    mutationFn: (req: GenerateRequest) => api.generate(req),
    onSuccess: (res) => {
      const n = Object.keys(res.tables).length;
      toast.success(`Generated ${n} table(s) (seed ${res.seed}, ${res.format})`);
    },
    onError: (e) => toast.error(errMessage(e)),
  });
}

export function useQuality() {
  return useMutation({
    mutationFn: api.quality,
    onError: (e) => toast.error(errMessage(e)),
  });
}

export function useSemantic() {
  return useMutation({
    mutationFn: (v: { name?: string; format?: string | null }) =>
      api.semantic(v.name, v.format),
    onError: (e) => toast.error(errMessage(e)),
  });
}

export function useSql() {
  return useMutation({
    mutationFn: (question: string) => api.sql(question),
    onError: (e) => toast.error(errMessage(e)),
  });
}

export function useDocs() {
  return useMutation({
    mutationFn: api.docs,
    onError: (e) => toast.error(errMessage(e)),
  });
}
