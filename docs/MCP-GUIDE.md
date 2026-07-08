# MCP Guide

Complete reference for the MCP (Model Context Protocol) integration: setup for every IDE, all 26 tools with parameters, agent flows, and example conversations.

The MCP server (`adp mcp-server`) is a thin adapter over the same `ADPClient` backend as the CLI, SDK, REST API, and Web UI. Every capability reachable from the CLI is reachable here.

See [GETTING-STARTED.md](GETTING-STARTED.md) for a runnable walkthrough of Path C (MCP from an AI IDE).  
See [AGENT-FLOW.md](AGENT-FLOW.md) for guided agent workflows (intake → research → spec → KPI validation).

---

## Setup

### Quick setup (all clients)

```bash
pip install 'ai-data-platform[mcp]'
cd my-project && adp init
adp setup-agent --client all   # re-sync; prints Claude Desktop snippet
```

This writes MCP configs for Cursor, Windsurf, and VS Code, plus Cursor skills in `.cursor/skills/adp-*`.

### Cursor

1. Install: `pip install 'ai-data-platform[mcp]'`
2. Run `adp init` in your project (auto-writes `.cursor/mcp.json` and skills), or create manually:

```json
// .cursor/mcp.json
{
  "mcpServers": {
    "adp": {
      "command": "adp",
      "args": ["mcp-server", "--project", "."]
    }
  }
}
```

3. Open the folder containing `adp.yaml` as your workspace root
4. Reload MCP: `Ctrl+Shift+P` → "Reload MCP"

The server auto-discovers the project from the workspace root (cwd). Optional override: `["mcp-server", "--project", "./subdir"]`.

### Claude Code CLI

```bash
adp setup-agent --client claude
# or manually:
claude mcp add adp -- adp mcp-server --project .
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "adp": {
      "command": "adp",
      "args": ["mcp-server"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

### Windsurf / VS Code

Run `adp init` or `adp setup-agent` — writes `.windsurf/mcp.json` and `.vscode/mcp.json`. Manual fallback:

```json
{
  "mcpServers": {
    "adp": {
      "command": "adp",
      "args": ["mcp-server"]
    }
  }
}
```

---

## Tool reference

All tools return structured JSON: `{"ok": true, "result": ...}` on success, `{"ok": false, "error": "..."}` on failure. Maximum rows per table via MCP: **1,000,000**.

### Design-time (spec authoring)

#### `propose_spec`

Ask the configured LLM to draft a dataset spec from a plain-language description.

```json
{
  "description": "A retail e-commerce dataset with customers, orders, and products",
  "research_notes": "Indian e-commerce: UPI 40% of payments, Delivered 82%, average order value $142"
}
```

**Returns:** `{"yaml": "...", "spec": {...}}` — schema-validated YAML ready to pass to `apply_spec`.

> **Tip:** Use your IDE's web search first to research real distributions, then pass findings as `research_notes`. Review the returned YAML before applying it.

#### `apply_spec`

Register a declarative spec and write `spec.yaml` into the project. After this, call `generate_synthetic_data`.

```json
{
  "spec_yaml": "version: 1\ntables:\n  - name: customers\n    columns:\n      - {name: customer_id, type: uuid, primary_key: true}\n..."
}
```

**Side effect:** Writes `spec.yaml` into the project directory.

---

### Catalog (sample data path)

#### `scan_sources`

Discover tables, columns, and FK candidates from configured sources in `adp.yaml`.

```json
{"source": null}   // null = all sources; or "my-source-name"
```

Use this after `adp connect` has been run (CLI) or when `sources` is already in `adp.yaml`.

#### `profile_source`

Compute statistics, detect PII, confirm PKs/FKs.

```json
{"source": null, "sample_rows": 10000}
```

**Returns:** per-table column statistics including null ratios, distinct counts, min/max/mean/std, top values, entropy, PII flags, and PK/FK confirmation.

#### `search_metadata`

Search the catalog for tables and columns by name.

```json
{"query": "customer", "limit": 20}
```

#### `get_table_schema`

Get full column details for one table.

```json
{"table": "fact_transaction"}
```

**Returns:** column name, data type, nullable, primary key, PII flags.

---

### Generation and validation

#### `generate_synthetic_data`

Generate FK-safe synthetic data into `output/`. Deterministic per seed.

```json
{
  "rows": 50000,
  "tables": null,
  "seed": null,
  "rows_per_table": {"dim_customer": 5000, "fact_transaction": 50000},
  "output_format": "parquet"
}
```

- `rows`: default count applied to any table without an override
- `rows_per_table`: per-table overrides (e.g. small dimension tables vs large fact tables)
- `seed`: reproducibility. Same seed = byte-identical output
- `output_format`: `parquet` (default), `csv`, `duckdb`, `sql`

**Side effect:** Writes files to `output/`; auto-registers parquet/CSV into DuckDB for Explorer.

#### `preview_data`

Inspect generated output (max 50 rows, token-budgeted).

```json
{"table": "customers", "limit": 10}
```

#### `run_quality_check`

Run all quality checks and return the score.

```json
{}
```

**Returns:**

```json
{
  "quality_score": 100,
  "category_scores": {"integrity": 1.0, "completeness": 1.0, "validity": 1.0, "consistency": 1.0},
  "failing_checks": []
}
```

Always finish with this after `generate_synthetic_data`.

---

### Artifacts

#### `create_semantic_model`

Build a Cube.js or generic semantic model YAML from the catalog.

```json
{"name": "default", "format": "cube"}
```

Formats: `cube` (Cube.js), `generic`.

#### `generate_sql`

Convert a natural-language question to a read-only DuckDB SELECT.

```json
{"question": "revenue by city last quarter"}
```

Requires `MINIMAX_API_KEY` or `OPENAI_API_KEY` configured. PII columns are excluded from prompts.

#### `generate_docs`

Generate a Markdown data dictionary for the full catalog.

```json
{}
```

---

### Data Explorer (DuckDB)

All Explorer tools operate on generated files registered as DuckDB views. No data is copied — views are live reads of the parquet/CSV files.

#### `register_datasets`

Manually (re)register files into DuckDB.

```json
{"dataset": "default", "data_dir": null}
```

Usually automatic after `generate_synthetic_data`. Call this to re-register after adding files manually.

#### `list_datasets`

List all registered datasets.

```json
{}
```

**Returns:** dataset name, table count, total rows, DuckDB file path.

#### `list_tables`

List tables within a dataset.

```json
{"dataset": "default"}
```

**Returns:** table name, format (parquet/csv), row count, column count, partition keys.

#### `describe_table`

Full metadata for one table.

```json
{"table": "customers", "dataset": "default"}
```

#### `show_schema`

DDL-style schema for a table.

```json
{"table": "customers", "dataset": "default"}
```

#### `preview_table`

Preview N rows from a table.

```json
{"table": "customers", "dataset": "default", "limit": 20}
```

Max 200 rows.

#### `get_row_count`

Exact row count for a table.

```json
{"table": "customers", "dataset": "default"}
```

#### `profile_table`

Per-column statistics (nulls, distinct, min/max/avg/stddev for numerics; top values for categoricals).

```json
{"table": "orders", "dataset": "default"}
```

#### `execute_sql`

Run a governed read-only SELECT.

```json
{"sql": "SELECT city, count(*) FROM customers GROUP BY city ORDER BY 2 DESC LIMIT 5", "dataset": "default", "max_rows": null}
```

**Guards enforced:**
- SELECT-only (writes rejected)
- Read-only DuckDB connection
- Row limit on result
- Query timeout
- Scan size limit

#### `explain_sql`

Return the query plan and estimated row count before executing.

```json
{"sql": "SELECT * FROM orders WHERE amount > 500", "dataset": "default"}
```

#### `suggest_analytics_queries`

Get suggested analytical SQL queries derived from the schema.

```json
{"dataset": "default", "table": "orders", "limit": 8}
```

When an LLM provider is configured, suggestions are enriched with model-generated ideas.

#### `generate_business_insights`

Execute a SELECT and get a natural-language summary: key findings, anomalies, trends, data quality notes, dashboard-ready metrics.

```json
{"sql": "SELECT status, count(*) FROM orders GROUP BY status", "dataset": "default"}
```

#### `validate_business_questions`

Check which business questions can be answered from the schema.

```json
{"questions": ["What is the average order value?", "What is the fraud rate?"], "dataset": "default"}
```

**Returns:** per-question answerability and a suggested starting SQL.

#### `export_query_result`

Run a SELECT and export the full result to a file.

```json
{"sql": "SELECT * FROM customers LIMIT 1000", "filename": "top_customers.csv", "dataset": "default", "format": "csv"}
```

Formats: `csv` (default), `parquet`, `json`. File written to the project's export directory (sandboxed — only a filename is accepted, never an arbitrary path).

---

## Resources

| URI | What it returns |
|---|---|
| `catalog://tables` | All cataloged tables as JSON |
| `catalog://relationships` | All inferred/confirmed FK relationships as JSON |

---

## Prompts

#### `research_and_generate`

Full research-driven generation workflow:

```
1. RESEARCH: use web search to find real-world facts about the domain
2. REASON: summarize as research notes with sources
3. DRAFT: propose_spec with description AND research notes
4. VALIDATE: review and adjust the YAML
5. APPLY: apply_spec
6. GENERATE: generate_synthetic_data
7. VALIDATE: run_quality_check
8. INSPECT: preview_data / generate_business_insights
```

#### `new_dataset_wizard`

Guides a user through creating a new dataset from scratch: domain description → spec proposal → apply → generate → quality check.

---

## Recommended agent flows

### Flow 1 — Spec-only (no data)

```
propose_spec (optional) → apply_spec → generate_synthetic_data → run_quality_check → preview_data
```

**Example prompt:**

> "Generate a healthcare dataset with 5 tables: patients, admissions, diagnoses, treatments, and discharges. Use realistic distributions — emergency admissions are 40%, average length of stay is 5 days."

### Flow 2 — From sample data

```
scan_sources → profile_source → generate_synthetic_data → run_quality_check → preview_data
```

**Example prompt:**

> "Scan my CSV source in `./data/`, profile it, and generate 50,000 rows. Run a quality check and show me the first 10 rows of each table."

### Flow 3 — Post-generation analytics

```
list_datasets → list_tables → profile_table → execute_sql / suggest_analytics_queries → generate_business_insights
```

**Example prompt:**

> "Register the generated data, give me a summary of the orders table (row count, column stats), and suggest 5 useful analytical queries. Then run the most interesting one and explain the findings."

### Flow 4 — Research-driven (via prompt)

```
research_and_generate prompt → propose_spec → apply_spec → generate_synthetic_data → run_quality_check
```

**Example prompt:**

> "Use the research_and_generate workflow to create a realistic Indian e-commerce dataset grounded in real payment market shares, delivery success rates, and category distributions from 2024-2025 data."

---

## Example agent conversations

### Spec-only generation with review loop

**User:** "Apply the customer-transaction spec and generate 20,000 rows."

**Agent calls:** `apply_spec(spec_yaml)` → `generate_synthetic_data(rows=20000)` → `run_quality_check()`

**User:** "Show me the first 10 rows and tell me the quality score."

**Agent calls:** `preview_data(table="fact_transaction", limit=10)` (quality already known from previous call)

---

### From data with quality failure

**User:** "Scan my source, profile it, and generate 50k rows."

**Agent calls:** `scan_sources()` → `profile_source(sample_rows=10000)` → `generate_synthetic_data(rows=50000)` → `run_quality_check()`

**User:** "Quality is only 82/100. What checks failed?"

**Agent calls:** `run_quality_check()` (already run; reads `failing_checks` from result)

**Agent:** "The failing checks are:
- `orders.total_amount`: value $1,842 exceeds mean+3σ ($1,200) — 12 outliers
- `customers.email`: 3 duplicate addresses

Recommendations: run `profile_source` with more rows to recalibrate distributions, or adjust the `max` value in your spec for `total_amount`."

---

### Full analytics session

**User:** "Register my generated output and give me insights on the orders table."

**Agent calls:** `register_datasets()` → `profile_table(table="orders")` → `execute_sql(sql="SELECT status, count(*), avg(amount) FROM orders GROUP BY status")` → `generate_business_insights(sql="SELECT date_trunc('month', order_date) as month, sum(amount) as revenue FROM orders GROUP BY 1 ORDER BY 1")`

**Agent:** "Orders table has 50,000 rows across 6 statuses. Key findings:
- Delivered: 41,000 (82%) — healthy fulfillment rate
- Returned: 1,500 (3%) — within normal e-commerce range
- Revenue trend: growing 8% QoQ, peak in November (holiday season)
- Average order value: $142.50, median $98 (right-skewed, a few high-value orders)
Dashboard-ready metrics: consider tracking AOV, delivery rate, and return rate as live KPIs."

---

## Internals

For DuckDB explorer design details (views vs copies, partitioning, metastore), see [MCP-DATA-EXPLORER.md](MCP-DATA-EXPLORER.md).
