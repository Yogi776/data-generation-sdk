# Universal Data Ingestion (DuckDB)

A metadata-driven ingestion engine: point it at any common industry file format —
local, folder, URL, or cloud — and it detects the format, infers the schema,
profiles the data, flags quality issues, creates a queryable DuckDB view/table,
and returns a full metadata report with ready-to-run SQL. **No domain logic is
hardcoded** — retail, healthcare, banking, manufacturing, oil & gas, logistics,
telecom, insurance, and custom domains all work through the same path.

Implementation: `src/ai_data_platform/ingestion/`. It is standalone — it owns its
own DuckDB database (`.adp/ingestion.duckdb`) and metadata registry
(`.adp/ingestion/`), independent of the rest of the platform.

---

## Architecture

```
Input Source (file | folder | URL | s3/gs/az)
  → Format Detector        detector.py      scheme, format, compression, delimiter/encoding, partitions, sheets
  → DuckDB Reader Selector duckdb_reader.py native scan expr | Arrow load; lazy extension install
  → Schema Inference       (DuckDB DESCRIBE)
  → Data Profiler          profiler.py      SUMMARIZE + aggregates: nulls, distinct, min/max/avg/std, duplicates, samples
  → Quality Validator      quality.py       warnings from the profile (domain-agnostic)
  → View/Table Creator     duckdb_reader.py CREATE VIEW (native, lazy) | CREATE TABLE AS (persist/loaded)
  → SQL Generator          sql_generator.py CREATE stmts, profiling/quality/sample SQL, schema JSON, docs
  → Metadata Export        metadata.py      report + per-source JSON + manifest
```

Orchestrated by `engine.py` (`IngestionEngine` / `ingest_data`).

---

## The universal function

```python
from ai_data_platform.ingestion import ingest_data

report = ingest_data(
    source_path: str,            # file, folder, glob, http(s) URL, or s3://|gs://|az:// path
    table_name: str | None = None,   # defaults to a sanitized name from the path
    persist: bool = False,       # True → CREATE TABLE AS (materialize); else lazy VIEW for native formats
    sample_size: int = 10_000,   # rows used for type inference
    options: dict | None = None, # see below
)
```

`options` keys (all optional): `project` (root dir for the DuckDB/registry),
`format` (force detection), `delimiter`, `has_header`, `encoding`, `sheet`
(Excel name or 0-based index), `flatten` + `record_path`/`sep`/`max_level`
(nested JSON), `sqlite_table`, `ignore_errors` (CSV), `quality` (threshold
overrides).

### Output (matches the requested schema)

```json
{
  "source_path": "examples/retail-ecommerce/data/orders.csv",
  "detected_format": "csv",
  "table_name": "orders",
  "relation_kind": "view",
  "persisted": false,
  "row_count": 10,
  "column_count": 8,
  "schema": [{"name": "order_id", "type": "BIGINT", "nullable": false}, "…"],
  "profile": {
    "row_count": 10, "column_count": 8, "duplicate_rows": 0,
    "duplicate_check": "exact",
    "columns": {"amount": {"type": "DOUBLE", "null_count": 2, "null_percentage": 20.0,
                            "distinct": 8, "min": 45.0, "max": 1299.0, "avg": 419.05}}
  },
  "quality_warnings": [{"code": "some_null", "severity": "warning",
                        "column": "amount", "message": "20.0% null."}],
  "sample_rows": [{"order_id": 1001, "…": "…"}],
  "sql_examples": [{"title": "…", "sql": "…"}],
  "generated": {
    "create_view": "…", "create_table_as": "…", "applied_ddl": "…",
    "profiling_sql": "…", "quality_sql": [{"title": "…", "sql": "…"}],
    "schema_export_json": "…", "documentation_markdown": "…"
  }
}
```

Use `adp ingest examples/retail-ecommerce/data/orders.csv --table orders` for a live walkthrough.

---

## Supported formats

| Format | How it's read | Relation | Notes |
|---|---|---|---|
| CSV / TSV / `.txt` | `read_csv_auto` | view | delimiter, header, encoding auto-detected; `.gz` supported |
| JSON | `read_json_auto` | view | nested STRUCT/LIST inferred; `flatten=True` → dotted columns (table) |
| NDJSON / JSONL | `read_json_auto(format='newline_delimited')` | view | |
| Parquet | `read_parquet` | view | folders/globs, hive partitions, predicate/projection pushdown |
| Excel (xlsx/xlsm/xls) | pandas + openpyxl/xlrd → Arrow | table | multi-sheet; `options={'sheet': name|index}` |
| Arrow / Feather / IPC | `pyarrow.feather` → Arrow | table | |
| ORC | `pyarrow.orc` → Arrow | table | |
| Avro | DuckDB `avro` ext, else `fastavro` → Arrow | view/table | graceful degrade |
| SQLite / `.db` | DuckDB `sqlite_scanner` (ATTACH) → materialize | table | `options={'sqlite_table': …}`; first table by default |
| PostgreSQL dump (`.sql`) | COPY-block parser → Arrow | table | subset; export CSV/Parquet for full dumps |
| Delta Lake | DuckDB `delta` ext (`delta_scan`) | view | optional extension |
| Iceberg | DuckDB `iceberg` ext (`iceberg_scan`) | view | optional extension |
| Compressed (gzip/zip/zstd/snappy) | native to reader | — | detected from extension |
| Folder / partitioned | glob + `hive_partitioning=true` | view | partition keys detected |
| Cloud (s3/gs/az/http) | DuckDB `httpfs`/`azure` | view | uses ambient credentials; installed at runtime |

**Native** formats become lazy **views** (streaming, pushdown, no full load).
**Loaded** formats (Excel/Arrow/ORC/Avro/SQLite/pg dump) are read into Arrow and
**materialized** as tables — the only way to keep them queryable across
connections. `persist=True` materializes native formats too.

Tiering: native formats (DuckDB/pyarrow) are always available; Delta, Iceberg,
Avro, and cloud rely on optional DuckDB extensions / Python packages installed on
demand and degrade with a clear `FormatDependencyError` if unavailable.

---

## CLI

```bash
adp ingest ./data/orders.csv --table orders --profile
adp ingest ./data/customers.xlsx --sheet Sheet1 --table customers
adp ingest s3://bucket/sales/*.parquet --table sales --persist
adp ingest ./events.ndjson --table events --flatten
adp list-sources
adp query "SELECT region, sum(amount) FROM sales GROUP BY region"
```

`adp query` runs a **read-only** SELECT against the ingestion DuckDB (row-capped).

---

## MCP tool design

So Claude / Cursor / other MCP clients can drive ingestion. All return the
platform envelope `{"ok": true, "result": …}` or `{"ok": false, "error": "…"}`.

| Tool | Purpose | Key inputs |
|---|---|---|
| `ingest_data` | detect + read + profile + register a source | `source_path`, `table_name?`, `persist?`, `sample_size?`, `options?` |
| `query_data` | read-only SELECT over ingested tables | `sql`, `max_rows?` |
| `list_ingested_sources` | list registered tables/views | — |
| `describe_ingested_source` | full stored metadata report | `table` |
| `preview_ingested` | first N rows | `table`, `limit?` |

Security: `query_data` and `adp query` accept a single SELECT/WITH only; a
denylist blocks DDL/DML, ATTACH/COPY/SET/INSTALL/LOAD/PRAGMA, and the connection
for reads is opened `read_only=True`. Results are row-capped with a `truncated`
flag. Ingestion writes only inside `.adp/`.

Example (agent flow):

```
ingest_data(source_path="s3://bucket/sales/*.parquet", table_name="sales", persist=false)
  → {detected_format: "parquet", row_count: 1200000, quality_warnings: [...], sql_examples: [...]}
query_data(sql="SELECT region, sum(amount) rev FROM sales GROUP BY 1 ORDER BY rev DESC")
  → {columns: ["region","rev"], rows: [...], truncated: false}
```

---

## Data quality warnings

Derived from the profile, domain-agnostic. Codes: `empty_table`,
`duplicate_rows`, `high_null` (≥50%), `some_null` (≥5%), `constant_column`,
`high_cardinality` (non-id, ≥90% distinct), `no_variance` (min == max). Each has a
`severity` (info | warning | high) and the affected `column`. Thresholds are
overridable via `options={"quality": {...}}`.

---

## Validation strategy

- **Per-format tests** — `tests/test_csv.py`, `test_excel.py`, `test_json.py`,
  `test_parquet.py`, `test_large_files.py`: detection (delimiter/header/encoding/
  gzip), view vs materialized table, profiling stats, quality warnings, generated
  SQL, JSON flattening, Parquet folders + hive partitions + pushdown, the SELECT
  guard, persistence, and large-file lazy-view + streaming behavior.
- **Determinism** — fixed sample generators keep assertions stable.
- **Graceful degradation** — optional formats raise a clear
  `FormatDependencyError` when their extension/package is absent (never a stack
  trace).
- **Gates** — `ruff` + `pytest` (CI). All ingestion tests pass on Python 3.11.

---

## Performance benchmarks

`python benchmarks/bench_ingestion.py --rows 1000000` (1M rows, local dev box):

| stage | ms |
|---|---|
| ingest CSV (view + profile) | ~1690 |
| ingest Parquet (view + profile) | ~630 |
| query group-by (full scan) | ~410 |
| query filter (limit 1k) | ~310 |

Registering a Parquet **view** is near-constant regardless of size (no load);
the cost is the one-time profiling scan. Parquet is preferred for large data.

---

## Folder structure

```
src/ai_data_platform/ingestion/
├── __init__.py         # exports ingest_data, IngestionEngine
├── detector.py         # scheme/format/compression/delimiter/encoding/partition/sheet detection
├── duckdb_reader.py    # reader selector, scan-expr builder, extensions, view/table creation, SELECT guard
├── excel_reader.py     # Excel → Arrow (multi-sheet, sheet selection)
├── json_flattener.py   # nested JSON → flat Arrow
├── pg_dump.py          # PostgreSQL COPY-block parser
├── profiler.py         # SUMMARIZE-based profiling
├── quality.py          # quality warnings
├── sql_generator.py    # CREATE/profiling/quality/sample SQL, schema JSON, docs
├── metadata.py         # report assembly + registry (per-source JSON + manifest)
├── engine.py           # IngestionEngine + ingest_data() orchestrator + query()
└── cli.py              # adp ingest / adp query / adp list-sources

tests/       test_csv.py  test_excel.py  test_json.py  test_parquet.py  test_large_files.py
examples/retail-ecommerce/data/   customers.csv  products.csv  orders.csv  transactions.csv
                      validation_report.orders.json
benchmarks/  bench_ingestion.py
```

---

## Error handling & logging

Every failure is a typed `IngestionError` subclass with a remediation hint
(`FormatDetectionError`, `UnsupportedFormatError`, `FormatDependencyError`).
Logging is via the platform logger (`adp.ingestion.*`) at INFO for lifecycle
events (detection, ingest timing) and for graceful-degradation notices.
```
