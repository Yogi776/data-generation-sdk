# MCP Data Explorer with DuckDB

Production feature design and reference for the `ai-data-platform` explorer:
after synthetic data is generated, files are registered into an embedded DuckDB
database and exposed through MCP so users can inspect metadata, query tables,
run analytical SQL, and get business insights — with no manual data loading.

This document is the contract. The implementation lives in
`src/ai_data_platform/explorer/` and is wired through the same `ADPClient`
backend as the CLI, REST API, and MCP server ("one backend, many faces").

---

## 1. Where it fits — updated architecture

The generation pipeline gains two stages (Registrar, Explorer) plus an Insight
agent. Nothing upstream changes; registration is a post-generation hook.

```
User Prompt
  → Domain Understanding      (LLM: interpret intent)
  → Prompt-to-Spec            (propose_spec → dataset spec YAML)
  → Data Model Designer       (tables, columns, keys)
  → Industry Rules Engine     (weights, ranges, formats, dependencies)
  → Synthetic Data Generator  (generator/: FK-safe, seeded → Parquet/CSV/JSON)
  → Data Quality Checker      (quality/: derived checks + score)
  → DuckDB Dataset Registrar  (explorer/registrar.py)   ← NEW
  → MCP Data Explorer         (explorer/engine.py + MCP tools)  ← NEW
  → SQL Analytics Agent       (governed SELECT execution)  ← NEW
  → Insight Generator         (explorer/insights.py)  ← NEW
```

Backend layering (all faces call `ExplorerService`):

```
 CLI (adp explore)   REST (/explorer/*)   MCP tools (13)
        └──────────────────┴───────────────────┘
                    ADPClient  (sdk.py)
                         │
                 ExplorerService  (explorer/service.py)
     ┌───────────────┬───────────────┬──────────────────┐
 DatasetRegistrar  DuckDBExplorer   InsightAgent    ExplorerMetastore
 (register views)  (governed SQL)   (analytics+LLM) (SQLite/Postgres)
        └───────── persistent DuckDB (.adp/explorer.duckdb) ──────┘
```

Design principles carried over from the platform: read-only by default,
deterministic, project-sandboxed writes, structured/actionable errors, and no
domain hardcoding (everything derives from the registered schema).

---

## 2. Dataset registration

`DatasetRegistrar.register_dir()` runs automatically at the end of
`generate_data()` when `explorer.enabled` and `explorer.auto_register` are true
and the output format is `parquet`, `csv`, or `json`.

- **Discovery** — scans the output directory. Each flat file becomes a table
  named by its stem. When the same table exists in multiple formats, priority is
  **parquet > json > csv** (Parquet preferred for scan performance).
- **Views, not copies** — each table is registered as a DuckDB **view** over the
  source file, e.g. `CREATE OR REPLACE VIEW orders AS SELECT * FROM
  read_parquet('…/orders.parquet')`. Views mean zero data duplication, always-
  fresh reads, and full Parquet predicate/projection pushdown.
- **Auto-detection** — columns, types, and nullability from `DESCRIBE`; exact
  row counts from `count(*)`.
- **Partitions** — a subdirectory containing hive-style `key=value/…parquet`
  is registered with `hive_partitioning=true` and its partition keys recorded.
- **Persistence** — the DuckDB database file is `.adp/explorer.duckdb`; dataset
  and table metadata are written to the explorer metastore (section 5).

Iceberg is intentionally out of scope for the MVP (the generator does not emit
it). The reader table in `registrar.py` (`_READERS`) is the single extension
point: add `iceberg_scan` there plus a catalog config to support it later.

---

## 3. DuckDB query layer design

`DuckDBExplorer` (`explorer/engine.py`) is the only component that reads from
DuckDB. Every query goes through the same governed path:

1. **Connect read-only** — `duckdb.connect(path, read_only=True)`. DDL/DML
   cannot execute at the engine level regardless of the SQL text.
2. **Guard** — `security.guard_select()` accepts a single `SELECT`/`WITH`,
   rejects a keyword denylist and file/remote reader functions.
3. **Scan guard** — `EXPLAIN` estimates the max cardinality; queries above
   `explorer.max_scan_rows` are refused before execution (best-effort).
4. **Bound** — `security.wrap_with_limit()` wraps the query to return at most
   `max_result_rows + 1` rows (the extra row detects truncation); large outputs
   are uniformly sampled with `USING SAMPLE reservoir(...)` when
   `sample_large_results` is on.
5. **Timeout** — a watchdog thread calls `con.interrupt()` after
   `query_timeout_seconds`; an interrupted query raises `QueryTimeoutError`.
6. **Log** — every attempt (ok / rejected / timeout / error) is appended to the
   query log with row count, truncation flag, and elapsed time.

Metadata operations (`describe`, `schema`, `preview`, `row_count`, `profile`)
resolve table existence through the metastore first, then read via the same
read-only connection. `profile_table` samples tables above 2M rows
(`reservoir(200k)`) and reports `sampled: true`.

**Temporary tables** are deliberately unsupported through `execute_sql`: the
read-only connection is a hard safety boundary. Reusable derived views are
created by the registrar, not by ad-hoc queries.

---

## 4. MCP tool contracts

13 tools, all returning the platform's envelope: `{"ok": true, "result": …}` on
success or `{"ok": false, "error": "message\nHint: …"}` on failure (handlers are
wrapped by `_safe`, so stack traces never leak). Input/output shapes below are
the `explorer/schemas.py` Pydantic models; call `Model.model_json_schema()` for
the full JSON Schema.

Security applies to **all** tools: read-only DuckDB connection; writes (export)
are sandboxed to the project export dir; PII-tagged data is never sent to an LLM
by the insight tools (only schema + aggregate result samples are).

### 4.1 `list_datasets`
- **Purpose** — discover registered datasets.
- **Input** — none.
- **Output** — `DatasetInfo[]`: `{dataset, created_at, table_count, total_rows, db_path, tables[]}`.
- **Request** — `list_datasets()`
- **Response** — `{"ok":true,"result":[{"dataset":"default","table_count":5,"total_rows":100500,"tables":["customers","order_items","orders","payments","products"], ...}]}`
- **Failure modes** — none typical (empty list if nothing registered).
- **Security** — read-only metastore.

### 4.2 `list_tables`
- **Purpose** — list tables in a dataset.
- **Input** — `{dataset="default"}`.
- **Output** — `RegisteredTable[]`: `{table, format, path, row_count, column_count, partitioned, partition_keys[]}`.
- **Request** — `list_tables(dataset="default")`
- **Response** — `{"ok":true,"result":[{"table":"orders","format":"parquet","row_count":100000,"column_count":6,"partitioned":false}]}`
- **Failure modes** — `DatasetNotFoundError` (unknown dataset).
- **Security** — read-only metastore.

### 4.3 `describe_table`
- **Purpose** — full table description incl. columns.
- **Input** — `{table, dataset="default"}`.
- **Output** — `DescribeResult`: `{table, dataset, format, path, row_count, columns[], partition_keys[]}`.
- **Request** — `describe_table(table="customers")`
- **Response** — `{"ok":true,"result":{"table":"customers","row_count":1000,"columns":[{"name":"customer_id","type":"BIGINT","nullable":false}, …]}}`
- **Failure modes** — `DatasetNotFoundError`, `ExplorerTableNotFoundError`.
- **Security** — read-only.

### 4.4 `show_schema`
- **Purpose** — schema as DDL + structured columns.
- **Input** — `{table, dataset="default"}`.
- **Output** — `SchemaResult`: `{table, ddl, columns[]}`.
- **Request** — `show_schema(table="orders")`
- **Response** — `{"ok":true,"result":{"ddl":"CREATE VIEW orders (\n  order_id BIGINT,\n  …\n);","columns":[…]}}`
- **Failure modes** — table/dataset not found.
- **Security** — read-only.

### 4.5 `preview_table`
- **Purpose** — sample the first N rows.
- **Input** — `{table, dataset="default", limit=20}` (limit ≤ 200).
- **Output** — `PreviewResult`: `{table, columns[], rows[], showing}`.
- **Request** — `preview_table(table="orders", limit=5)`
- **Response** — `{"ok":true,"result":{"columns":["order_id","total_amount"],"rows":[{"order_id":1,"total_amount":54.2}],"showing":5}}`
- **Failure modes** — table not found.
- **Security** — read-only; row cap enforced.

### 4.6 `get_row_count`
- **Purpose** — exact row count.
- **Input** — `{table, dataset="default"}`.
- **Output** — `RowCountResult`: `{table, row_count}`.
- **Request** — `get_row_count(table="orders")`
- **Response** — `{"ok":true,"result":{"table":"orders","row_count":100000}}`
- **Failure modes** — table not found.
- **Security** — read-only.

### 4.7 `profile_table`
- **Purpose** — per-column statistics.
- **Input** — `{table, dataset="default"}`.
- **Output** — `ProfileResult`: `{table, row_count, sampled, columns:[{column,type,null_count,null_fraction,distinct,min,max,mean,stddev,top_values[]}]}`.
- **Request** — `profile_table(table="orders")`
- **Response** — `{"ok":true,"result":{"row_count":100000,"sampled":false,"columns":[{"column":"total_amount","mean":57.3,"min":1.2,"max":980.0,"null_fraction":0.0}]}}`
- **Failure modes** — table not found.
- **Security** — read-only; tables > 2M rows sampled (`sampled:true`).

### 4.8 `execute_sql`
- **Purpose** — run governed analytical SQL.
- **Input** — `SqlRequest`: `{sql, dataset="default", max_rows?}`.
- **Output** — `SqlResult`: `{columns[], rows[], row_count, truncated, sampled, elapsed_ms}`.
- **Request** — `execute_sql(sql="SELECT status, count(*) n FROM orders GROUP BY 1")`
- **Response** — `{"ok":true,"result":{"columns":["status","n"],"rows":[{"status":"completed","n":81000}],"row_count":3,"truncated":false,"elapsed_ms":4.1}}`
- **Failure modes** — `UnsafeSQLError` (non-SELECT/forbidden), `QueryTimeoutError`, `QueryTooLargeError`, `DatasetNotFoundError`.
- **Security** — read-only connection + SELECT-only guard + row limit + scan guard + timeout + logging; raw file readers blocked.

### 4.9 `explain_sql`
- **Purpose** — plan and cost before running.
- **Input** — `{sql, dataset="default"}`.
- **Output** — `ExplainResult`: `{plan, estimated_rows}`.
- **Request** — `explain_sql(sql="SELECT * FROM orders WHERE total_amount > 500")`
- **Response** — `{"ok":true,"result":{"plan":"…","estimated_rows":12000}}`
- **Failure modes** — `UnsafeSQLError`, dataset not found.
- **Security** — read-only; guard applied (EXPLAIN does not execute the query).

### 4.10 `suggest_analytics_queries`
- **Purpose** — propose ready-to-run analytics.
- **Input** — `SuggestRequest`: `{dataset="default", table?, limit=8}` (≤25).
- **Output** — `SuggestResult`: `{dataset, suggestions:[{title,sql,rationale,category}], source}` where `source ∈ {deterministic, hybrid}`.
- **Request** — `suggest_analytics_queries(dataset="default")`
- **Response** — `{"ok":true,"result":{"suggestions":[{"title":"Monthly total_amount — orders","sql":"SELECT date_trunc('month', order_date) …","category":"trend"}],"source":"deterministic"}}`
- **Failure modes** — dataset not found.
- **Security** — schema only sent to LLM (never row data); LLM optional, degrades to deterministic.

### 4.11 `generate_business_insights`
- **Purpose** — execute a query and summarize it.
- **Input** — `InsightRequest`: `{sql, dataset="default"}`.
- **Output** — `InsightResult`: `{summary, insights:[{kind,message}], dashboard_metrics[], recommended_queries[], result_preview, source}`; `kind ∈ {finding, anomaly, trend, data_quality}`.
- **Request** — `generate_business_insights(sql="SELECT date_trunc('month', order_date) m, sum(total_amount) rev FROM orders GROUP BY 1 ORDER BY 1")`
- **Response** — `{"ok":true,"result":{"summary":"Query returned 12 rows … rev: min=507, max=2659, avg=1590.","insights":[{"kind":"trend","message":"rev is increasing across the result."}],"dashboard_metrics":[{"label":"sum_rev","value":19080.9}],"source":"deterministic"}}`
- **Failure modes** — `UnsafeSQLError`, `QueryTimeoutError`, dataset not found.
- **Security** — runs through `execute_sql` governance; only aggregate sample + findings sent to the LLM.

### 4.12 `validate_business_questions`
- **Purpose** — judge which NL questions the data can answer.
- **Input** — `ValidateRequest`: `{questions[], dataset="default"}`.
- **Output** — `ValidateResult`: `{dataset, verdicts:[{question, answerable, reason, suggested_sql?, tables_needed[]}]}`.
- **Request** — `validate_business_questions(questions=["orders per status?","weather tomorrow?"])`
- **Response** — `{"ok":true,"result":{"verdicts":[{"question":"orders per status?","answerable":true,"tables_needed":["orders"]},{"question":"weather tomorrow?","answerable":false}]}}`
- **Failure modes** — dataset not found.
- **Security** — schema/metadata only.

### 4.13 `export_query_result`
- **Purpose** — write a query result to a file.
- **Input** — `ExportRequest`: `{sql, filename, dataset="default", format=csv|parquet|json}`.
- **Output** — `ExportResult`: `{path, format, row_count}`.
- **Request** — `export_query_result(sql="SELECT * FROM customers", filename="cust.csv", format="csv")`
- **Response** — `{"ok":true,"result":{"path":"…/exports/cust.csv","format":"csv","row_count":1000}}`
- **Failure modes** — `UnsafeSQLError`, `UnsafePathError` (path escape attempt), timeout.
- **Security** — only a **filename** is accepted; destination is sandboxed under the project export dir via `safe_resolve`; SELECT-guarded; timeout + scan guard applied.

---

## 5. Metadata catalog design

`ExplorerMetastore` (`explorer/metastore.py`), SQLAlchemy ORM. Local SQLite at
`.adp/explorer_catalog.db` by default; set `explorer.metadata_dsn` (with
`${ENV_VAR}` credentials) to use Postgres — the ORM is dialect-agnostic, so this
is a config change, not a code change.

| Table | Purpose | Key columns |
|---|---|---|
| `explorer_datasets` | one row per registered dataset | `name` (unique), `db_path`, timestamps |
| `explorer_tables` | one row per registered table/view | `dataset_id`, `name`, `file_format`, `path`, `row_count`, `partitioned`, `partition_keys` |
| `explorer_columns` | column-level schema | `table_id`, `name`, `data_type`, `nullable`, `ordinal` |
| `explorer_query_log` | append-only audit of executed SQL | `dataset`, `sql`, `status`, `row_count`, `truncated`, `elapsed_ms`, `error`, `created_at` |

The metastore is the source of truth for "what exists"; DuckDB is the execution
engine. Table existence is validated against the metastore before any DuckDB
read, giving clean `ExplorerTableNotFoundError` messages instead of raw engine
errors.

---

## 6. Security model

Layered, no single control trusted alone:

1. **Read-only engine** — DuckDB opened `read_only=True` for all reads; mutation
   is physically impossible.
2. **Statement guard** — one `SELECT`/`WITH` only; denylist blocks
   INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE, and
   COPY/ATTACH/DETACH/INSTALL/LOAD/PRAGMA/SET/EXPORT/CHECKPOINT/USE.
3. **File-reader block** — `read_csv/read_parquet/read_json/glob/…` rejected in
   user SQL so queries can't read arbitrary paths or reach the network; data is
   reached only through registered views.
4. **Result bounding** — `max_result_rows` cap with truncation flag and optional
   reservoir sampling so large outputs stay small and representative.
5. **Scan guard** — `EXPLAIN`-estimated cardinality above `max_scan_rows` is
   refused pre-execution.
6. **Timeout** — wall-clock `query_timeout_seconds` via `con.interrupt()`.
7. **Sandboxed writes** — export accepts a filename only; the path is resolved
   under the project export dir (`safe_resolve` rejects traversal).
8. **Audit log** — every query (incl. rejected/timeout) recorded.
9. **PII discipline** — insight/suggestion tools send only schema and aggregate
   result samples to the LLM; the LLM is always optional and failures degrade to
   deterministic output.

Config (`adp.yaml → explorer`): `enabled`, `auto_register`, `db_filename`,
`max_result_rows` (1000), `query_timeout_seconds` (30), `max_scan_rows` (50M),
`sample_large_results` (true), `metadata_dsn`.

---

## 7. SQL & metadata examples

Metadata exploration maps directly to tools:

| Ask | Tool |
|---|---|
| What datasets are available? | `list_datasets` |
| What tables exist? | `list_tables` |
| Describe the customer table | `describe_table("customers")` |
| Show the schema | `show_schema("customers")` |
| Column null counts / top values / min-max-avg | `profile_table("orders")` |
| Date range of a column | `profile_table` (temporal min/max) |
| Which columns can be used for joins? | `suggest_analytics_queries` (join suggestions) |

Analytics (run via `execute_sql`; templates from `suggest_analytics_queries`):

```sql
-- Top customers by revenue
SELECT c.customer_id, sum(o.total_amount) AS revenue
FROM orders o JOIN customers c USING (customer_id)
GROUP BY 1 ORDER BY revenue DESC LIMIT 20;

-- Monthly revenue by category
SELECT date_trunc('month', o.order_date) AS month, p.category,
       sum(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN orders o   USING (order_id)
JOIN products p USING (product_id)
GROUP BY 1, 2 ORDER BY 1, 2;

-- Claim denial rate (healthcare)
SELECT round(100.0 * count(*) FILTER (WHERE status = 'denied') / count(*), 2) AS denial_pct
FROM fact_claim;

-- Inventory shortage
SELECT product_id, stock_on_hand FROM inventory WHERE stock_on_hand < reorder_point;

-- Segment comparison
SELECT segment, count(*) AS customers, avg(total_amount) AS avg_order
FROM orders JOIN customers USING (customer_id) GROUP BY 1;
```

Churn/fraud/worst-performers follow the same pattern (filter + aggregate +
rank). The insight agent then summarizes findings, flags anomalies (e.g. a max
> 5× the mean), notes nulls/truncation, and recommends follow-ups.

---

## 8. Validation strategy

- **Unit/integration** — `tests/test_explorer.py`: auto-registration on
  generate, list/describe/schema, preview/count, `execute_sql` happy path, row-
  limit truncation, `explain`, `profile`, `export`, the security guard
  (parametrized rejects for DDL/DML/COPY/ATTACH/PRAGMA/SET/file-readers/multi-
  statement), and insights (suggest/insights/validate). All green on Python
  3.11 with the full suite.
- **Guard fuzzing** — extend the parametrized reject list as new SQL surfaces
  appear; the guard is pure and fast to test in isolation.
- **Determinism** — same seed ⇒ same generated files ⇒ same registered views ⇒
  reproducible query results, so insight assertions are stable.
- **Degradation** — insight tools verified to fall back to deterministic output
  when no LLM key is present (observed in the e2e smoke run).
- **Pre-release** — `ruff check` + `mypy` + `pytest` in CI (existing gates).

---

## 9. Folder structure

```
src/ai_data_platform/explorer/
├── __init__.py        # exports ExplorerService
├── schemas.py         # Pydantic IO contracts for all 13 tools
├── metastore.py       # dataset/table/column/query-log ORM (SQLite/Postgres)
├── registrar.py       # discover files → CREATE VIEW in DuckDB + metastore
├── security.py        # guard_select() + wrap_with_limit()
├── engine.py          # DuckDBExplorer: governed query + metadata + profile + export
├── insights.py        # InsightAgent: deterministic analytics + optional LLM
└── service.py         # ExplorerService facade (the single backend)

wired into:
  config.py            # ExplorerConfig
  sdk.py               # ADPClient.explorer + explorer methods + auto-register
  mcp/server.py        # 13 MCP tools
  api/app.py           # /explorer/* REST endpoints
  cli.py               # `adp explore …` command group
  core/exceptions.py   # ExplorerError, DatasetNotFoundError, QueryTimeoutError, …
tests/test_explorer.py # unit + integration + security + insights
```

---

## 10. End-to-end example

```
User: Generate retail customer/order/product data.
  → adp generate-data --rows 100000 --output parquet
  → generator writes customers/products/orders/order_items/payments.parquet
  → auto-register: 5 views created in .adp/explorer.duckdb

User (MCP): list_tables
  → ["customers","order_items","orders","payments","products"]

User (MCP): execute_sql
  SELECT date_trunc('month', o.order_date) AS month, p.category,
         sum(oi.quantity * oi.unit_price) AS revenue
  FROM order_items oi JOIN orders o USING (order_id)
  JOIN products p USING (product_id)
  GROUP BY 1,2 ORDER BY 1,2;
  → {columns:[month,category,revenue], rows:[…], truncated:false, elapsed_ms:12.4}

Insight Agent (generate_business_insights on the same SQL):
  summary: "Revenue is concentrated in 3 categories; electronics trends up Q3."
  insights: [{trend:"revenue increasing"}, {anomaly:"Nov spike >5× mean"}]
  dashboard_metrics: [{sum_revenue: …}, {avg_revenue: …}]
  recommended_queries: [top categories, MoM growth, per-customer revenue]
```

---

## 11. MVP implementation plan (status)

| # | Milestone | Status |
|---|---|---|
| 1 | `ExplorerConfig` + Pydantic tool schemas | ✅ done |
| 2 | Metastore (SQLite default, Postgres via DSN) | ✅ done |
| 3 | Registrar: csv/parquet/json → DuckDB views + partitions | ✅ done |
| 4 | Security guard + result bounding | ✅ done |
| 5 | DuckDBExplorer: query/describe/schema/preview/count/profile/explain/export | ✅ done |
| 6 | Insight agent (deterministic + optional LLM) | ✅ done |
| 7 | Wire SDK + 13 MCP tools + REST + `adp explore` CLI + auto-register | ✅ done |
| 8 | Tests + this design doc + verification (pytest/ruff/e2e) | ✅ done |
| — | **Future**: Iceberg registration, per-user quotas, saved queries, result caching, dashboard export to the Next.js UI | ⬜ backlog |
```
