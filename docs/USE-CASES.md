# Use Cases

Sixteen scenarios the platform covers, each with goal, best path, prerequisites, the exact commands to run, which example project to reference, and the expected outcome.

For a runnable step-by-step tutorial covering all paths, see [GETTING-STARTED.md](GETTING-STARTED.md).

---

## Which example should I use?

| Example | Tables | Columns | Domain | Best path |
|---|---|---|---|---|
| [customer-transaction](examples/customer-transaction/) | 2 (+ KYC) | 98 | CRM | A or B |
| [retail-ecommerce](examples/retail-ecommerce/) | 4 | ~30 | E-commerce | B — CSV |
| [healthcare-claims](https://github.com/Yogi776/data-generation-sdk/tree/main/healthcare-claims) | 5 | 159 | Healthcare | A — spec-only |
| [retail/](../retail/) (sibling project) | 4 | ~30 | Retail | A — spec-only |

---

## Use Case 1 — Generate test data with zero source files

**Goal:** Get realistic FK-safe synthetic data without having any real data at all.

**Best path:** A — spec-only

**Prerequisites:** `adp init --name my-project`

**Commands:**

```bash
adp init --name my-project
# Download the healthcare-claims spec from the GitHub repo or copy from your workspace:
# https://github.com/Yogi776/data-generation-sdk/blob/main/healthcare-claims/spec.yaml
adp apply-spec spec.yaml
adp generate-data --rows 50000 --output parquet
adp quality-check --report quality.md
```

**Example project:** The [healthcare-claims](https://github.com/Yogi776/data-generation-sdk/tree/main/healthcare-claims) GitHub example (9 tables, 200+ columns).

**Expected outcome:** Zero orphans across all FK chains; distributions match declared weights (e.g., payment UPI ~40%, Delivered ~82%); quality score ≥ 95.

---

## Use Case 2 — Clone production schema distributions from samples

**Goal:** Take your real CSV/DB exports and generate large volumes of data that preserve the statistical shapes.

**Best path:** B — learn from data

**Prerequisites:** Representative CSVs in `./data/`, 100+ rows per table recommended

**Commands:**

```bash
adp init --name my-project
adp connect --name my-db --type csv --path ./data
adp scan && adp profile --sample-rows 20000
adp generate-data --rows 100000 --output parquet
adp quality-check
```

**Example project:** `examples/retail-ecommerce` (4 tables, 32/32 checks, 100/100 quality)

**Expected outcome:** Learned distributions (lognormal for money, Poisson for counts, weighted categoricals); FK integrity preserved at scale; quality score reflects sample fidelity.

---

## Use Case 3 — Quick 2-minute demo

**Goal:** Show the platform working end-to-end as fast as possible.

**Best path:** B — CSV (from sample files)

**Prerequisites:** Any CSV files in `./data/` directory

**Commands:**

```bash
# Place your CSV files in ./data/ (e.g. customers.csv, orders.csv)
adp init --name demo-project
adp connect --name shop --type csv --path ./data
adp scan && adp profile
adp generate-data --rows 10000 --output parquet
adp quality-check
```

**Example project:** `examples/customer-transaction` (includes `data/` directory with sample CSVs)

**Expected outcome:** ~2 minutes total; tables detected from CSVs; FK candidates inferred from column names; quality score printed.

---

## Use Case 4 — Large multi-table e-commerce model (98 columns)

**Goal:** A full customer + transaction model with realistic proportions (payment mix, order statuses, ratings, coupon usage, fraud rate).

**Best path:** A (spec-only) or B (from CSV)

**Prerequisites:** `adp init`

**Commands (spec-only):**

```bash
cd examples/customer-transaction
adp apply-spec spec.yaml
adp generate-data --rows 50000 --output parquet
adp quality-check
```

**Commands (from CSV):**

```bash
cd examples/customer-transaction
python make_data.py
adp init --force
adp connect --name crm --type csv --path ./data
adp scan && adp profile
adp generate-data --rows 50000
adp quality-check
```

**Example project:** `examples/customer-transaction`

**Validated targets (50k rows):**

| Target | Spec | Generated |
|---|---|---|
| Gender M/F/O | 48/50/2 | 45.8/51.5/2.7 |
| Payment UPI/CC/DC/Wal/COD/PayPal | 40/22/15/10/8/5 | 40.0/21.8/15.0/9.6/8.3/5.3 |
| Order status Del/Ship/Proc/Canc/Ret | 82/6/5/4/3 | 81.9/5.9/5.1/4.0/3.1 |
| FK orphans | 0 | 0 |

**Expected outcome:** Quality score 100/100; temporal ordering validated (payment ≥ order in 100% of rows); `null_unless` conditional fields correct; `values_by` hierarchy (city-state) consistent.

---

## Use Case 5 — Healthcare with temporal and hierarchy rules

**Goal:** Multi-table healthcare schema with temporal ordering (discharge after admission), hierarchical categoricals (city within state), and conditional nulls.

**Best path:** A — spec-only

**Prerequisites:** `adp init`

**Commands:**

```bash
# Get the healthcare-claims spec from the GitHub repo:
# https://github.com/Yogi776/data-generation-sdk/blob/main/healthcare-claims/spec.yaml
adp apply-spec spec.yaml
adp generate-data --rows 50000 --output parquet
adp quality-check
```

**Example project:** The [healthcare-claims](https://github.com/Yogi776/data-generation-sdk/tree/main/healthcare-claims) GitHub example demonstrates all three features.

**Key spec features used:**

```yaml
# Temporal: discharge always after admission
- name: discharge_date
  type: datetime
  after: {column: admission_date, min_minutes: 60, max_minutes: 43200}

# Hierarchy: city always consistent with state
- name: city
  type: string
  values_by:
    column: state
    mapping:
      Maharashtra: {Mumbai: 55, Pune: 35, Nagpur: 10}
      Karnataka: {Bangalore: 80, Mysore: 20}

# Conditional null: refund_reason only for Returned
- name: refund_reason
  type: string
  values: {damaged: 30, wrong_item: 25, not_as_described: 25, size_issue: 20}
  null_unless: order_status = 'Returned'
```

**Expected outcome:** 5+ tables, 150+ columns, quality score ≥ 95; temporal ordering 100% valid; city-state consistency across all rows.

---

## Use Case 6 — Retail 4-table star schema

**Goal:** Retail star schema with `dim_customer`, `dim_product`, `fact_order`, `fact_order_item` — dimension and fact table pattern.

**Best path:** A — spec-only (or B from CSV)

**Prerequisites:** `adp init`; spec at `../../retail/spec.yaml` (relative from `docs/`)

**Commands:**

```bash
mkdir retail-project && cd retail-project
adp init --name retail-project
cp ../../retail/spec.yaml .
adp apply-spec spec.yaml
adp generate-data --rows 50000 --output csv
adp quality-check
```

**Example project:** `../../retail/` (sibling workspace project — same schema, pre-validated)

**Schema structure:**
```
dim_customer   (PK: customer_id)
dim_product    (PK: product_id)
fact_order     (PK: order_id, FK: customer_id → dim_customer)
fact_order_item (FK: order_id → fact_order, product_id → dim_product)
```

**Expected outcome:** 4 parquet/CSV files in `output/`; FK chain intact (`fact_order_item → fact_order → dim_customer`); 0 orphans; quality score printed.

---

## Use Case 7 — Drive everything from Cursor/Claude via MCP

**Goal:** Let an AI IDE agent handle the entire pipeline: spec authoring, generation, quality validation, and data inspection.

**Best path:** C — MCP

**Prerequisites:** `pip install 'ai-data-platform[mcp]'`; `.cursor/mcp.json` configured

**Commands (IDE prompts):**

> "Apply the healthcare spec and generate 10,000 rows of test data. Run a quality check when done."

Tool sequence: `apply_spec` → `generate_synthetic_data` → `run_quality_check`

> "Scan my CSV source, profile it, and generate 50,000 rows. Run a quality check."

Tool sequence: `scan_sources` → `profile_source` → `generate_synthetic_data` → `run_quality_check`

**Example project:** `cursor-test/`

**Expected outcome:** Agent reports quality score and per-table check results; generated files in `output/`; agent can follow up with `preview_data` to show sample rows.

See [MCP-GUIDE.md](MCP-GUIDE.md) for all 25 available MCP tools and 4 recommended agent flows.

---

## Use Case 8 — Reproducible CI generation (fixed seed)

**Goal:** Generate identical synthetic data in every CI run — same seed always produces byte-identical output.

**Best path:** A or B

**Prerequisites:** Either `apply-spec` or `scan`+`profile` completed

**Commands:**

```bash
# Always the same output
adp generate-data --rows 50000 --seed 42 --output parquet

# Different data, same shapes
adp generate-data --rows 50000 --seed 123
```

**Example project:** Any

**Expected outcome:** Running `--seed 42` twice on the same catalog produces bit-identical files. CI pipelines can pin `--seed 42` for reproducibility.

---

## Use Case 9 — Output to DuckDB / CSV / SQL instead of Parquet

**Goal:** Choose a different output format for downstream tooling compatibility.

**Best path:** Any

**Prerequisites:** Generation step

**Commands:**

```bash
# DuckDB (single database file with all tables as views)
adp generate-data --rows 50000 --output duckdb

# CSV (one file per table)
adp generate-data --rows 50000 --output csv

# SQL INSERT statements
adp generate-data --rows 1000 --output sql
```

**Example project:** Any

**Expected outcome:** `output/` contains `*.duckdb`, `*.csv`, or `*.sql` respectively. DuckDB output auto-registers into the Explorer.

---

## Use Case 10 — Connect PostgreSQL/MySQL as source

**Goal:** Use a live database as the source for schema learning.

**Best path:** B — from data

**Prerequisites:** PostgreSQL or MySQL accessible; `pip install 'ai-data-platform[postgres]'` or `[mysql]`

**Commands:**

```bash
# PostgreSQL
export PGPASSWORD=yourpassword    # use .env instead of plaintext in production
adp connect --name prod --type postgres \
  --dsn "postgresql+psycopg://user:${PGPASSWORD}@localhost:5432/mydb" \
  --schema public

# MySQL
export MYSQLPASSWORD=yourpassword
adp connect --name prod --type mysql \
  --dsn "mysql+pymysql://user:${MYSQLPASSWORD}@localhost:3306/mydb"
```

> **Security note:** Always use `${ENV_VAR}` in DSN strings. Plaintext passwords are rejected at load.

**Example project:** References in README connectors section

**Expected outcome:** Connected source appears in `adp.yaml`; `adp scan` discovers tables from the live database; SELECT-only — no data is modified.

---

## Use Case 11 — Build Cube.js semantic layer

**Goal:** Generate a semantic model (facts, dimensions, measures, joins) ready for Cube.js or a generic BI tool.

**Best path:** Post-generation

**Prerequisites:** `generate-data` completed with the catalog populated

**Commands:**

```bash
adp semantic-model --format cube --out model/cubes.yml
# Or for generic YAML:
adp semantic-model --format generic --out model/semantic.yml
```

**Example project:** `examples/retail-ecommerce` (includes `model/cubes.yml`)

**Expected outcome:** `model/cubes.yml` with `datasets`, `joins`, `preAggregations`; facts vs dims inferred from FK density; measures auto-generated per numeric column.

---

## Use Case 12 — Query generated data in natural language

**Goal:** Ask business questions in plain English and get read-only SQL back.

**Best path:** Post-generation (requires LLM API key)

**Prerequisites:** `MINIMAX_API_KEY` or `OPENAI_API_KEY` set; `generate-data` done

**Commands:**

```bash
export MINIMAX_API_KEY=your_key_here
adp sql "revenue by city last quarter"
# Returns: SELECT city, sum(amount) FROM orders WHERE order_date >= ... GROUP BY city
```

Or via MCP: `generate_sql` tool

**Example project:** Any with orders/data

**Expected outcome:** DuckDB-dialect SELECT; PII columns never sent to LLM; query is read-only (SELECT-only guard enforced).

---

## Use Case 13 — Validate data quality with a scored report

**Goal:** Get a quantitative quality score and per-check evidence for generated data.

**Best path:** Post-generation

**Prerequisites:** `generate-data` completed

**Commands:**

```bash
adp quality-check --report quality.md
# Or with custom data directory:
adp quality-check --data-dir ./output --report quality.md
```

**Quality score breakdown:**

| Category | Weight | What it checks |
|---|---|---|
| Integrity | 35% | PK uniqueness, FK inclusion (0 orphans) |
| Completeness | 25% | Not-null constraints, no missing FKs |
| Validity | 25% | Range + tolerance vs profile, accepted values |
| Consistency | 15% | Cross-column relationships, shape fidelity |

**Example project:** All examples produce quality reports (e.g., `examples/retail-ecommerce/quality-report.md`)

**Expected outcome:** `quality.md` with score, per-table pass/fail, and failing checks with evidence.

---

## Use Case 14 — Explore and analyze with SQL (CLI or MCP)

**Goal:** Inspect generated data with analytical SQL — no BI tool needed.

**Best path:** D — Explorer (after any generate)

**Prerequisites:** `generate-data` completed (auto-registers files into DuckDB)

**Commands (CLI):**

```bash
adp explore datasets
adp explore tables
adp explore sql "SELECT city, count(*) FROM customers GROUP BY city ORDER BY 2 DESC LIMIT 5"
adp explore describe orders
adp explore count orders
adp explore profile orders
adp explore suggest transactions
adp explore export "SELECT * FROM customers LIMIT 100" top_customers.csv
```

**Commands (MCP equivalents):**

```
list_datasets → list_tables → execute_sql → describe_table → get_row_count → profile_table → suggest_analytics_queries → export_query_result
```

**Example project:** Any

**Expected outcome:** DuckDB views over `output/` parquet/CSV files; zero data copy (views are live); governed SELECT-only execution.

See [MCP-GUIDE.md](MCP-GUIDE.md) for all 13 Explorer MCP tools.

---

## Use Case 15 — Python SDK in a script or notebook

**Goal:** Embed generation into a Python script, CI pipeline, or Jupyter notebook.

**Best path:** SDK (any entry path)

**Prerequisites:** `pip install ai-data-platform`

**Commands:**

```python
from ai_data_platform import ADPClient

# Path A: spec-based
client = ADPClient(".")
client.apply_spec("spec.yaml")
result = client.generate_data(rows=50_000, output_format="parquet")

# Path B: from data
client = ADPClient("examples/retail-ecommerce")
client.scan()
client.profile()
result = client.generate_data(rows=50_000)
score = client.quality_check()["quality_score"]

# Post-generation analytics
client.register_datasets()
tables = client.list_explorer_tables()
df = client.execute_explorer_sql("SELECT * FROM customers LIMIT 5")
```

**Example project:** `examples/customer-transaction/` (includes CSV sample data and adp.yaml)

**Expected outcome:** Full pipeline controllable programmatically; results returned as dicts; Explorer accessible via SDK.

---

## Use Case 16 — Browse via Web UI

**Goal:** Visual interface to browse catalog, inspect schemas, and view generated data.

**Best path:** UI (after any generate)

**Prerequisites:** `generate-data` completed

**Commands:**

```bash
adp ui
# → http://127.0.0.1:8765
```

**Expected outcome:** Browser opens to local web console; catalog tables listed; generated files browsable; no external network required.
