// Response shapes mirror the FastAPI backend (ai_data_platform/api/app.py),
// which is a thin layer over ADPClient. Keep in sync with the catalog/quality
// return dicts.

export interface Health {
  status: string;
  version: string;
}

export interface Source {
  name: string;
  type: string;
  tables: number;
  last_scanned_at: string | null;
}

export interface TableSummary {
  table: string;
  source: string;
  columns: number;
  row_count: number | null;
  kind: string;
  description: string | null;
}

export type PiiLevel = string | null;

export interface Column {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
  pii: PiiLevel;
  description: string | null;
}

export interface TableDetail {
  id: number;
  table: string;
  source: string;
  schema: string | null;
  row_count: number | null;
  kind: string;
  description: string | null;
  columns: Column[];
}

export type SearchResult =
  | {
      match: "table";
      table: string;
      source: string;
      description: string | null;
    }
  | {
      match: "column";
      table: string;
      column: string;
      source: string;
      type: string;
    };

export interface ScanResult {
  source: string;
  tables: number;
  [k: string]: unknown;
}

export interface ProfileResult {
  table: string;
  columns?: number;
  [k: string]: unknown;
}

export interface GenerateRequest {
  rows?: number | null;
  tables?: string[] | null;
  seed?: number | null;
  output_format?: string | null;
}

export interface GeneratedTable {
  rows: number;
  path: string;
}

export interface GenerateResult {
  seed: number;
  format: string;
  tables: Record<string, GeneratedTable>;
}

export interface QualityCheck {
  rule_type: string;
  params: Record<string, unknown>;
  category: string;
  passed: boolean;
  evidence: string;
}

export interface QualityTableReport {
  table: string;
  checks: QualityCheck[];
  passed: number;
  total?: number;
  [k: string]: unknown;
}

export interface QualityReport {
  score_version: number;
  quality_score: number;
  weights: Record<string, number>;
  category_scores: Record<string, number>;
  tables: QualityTableReport[];
}

export interface SemanticResult {
  model: Record<string, unknown>;
  rendered: string;
  format: string;
}

export interface SqlResult {
  sql: string;
  explanation: string;
  confidence: number;
  tables_used: string[];
}

export interface DocsResult {
  markdown: string;
}
