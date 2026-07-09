# Ai-data-platform

## Why it matters

Data is the prerequisite for every analytics dashboard, ML model, pipeline test, and stakeholder demo — yet most teams spend weeks waiting for it. Production exports require compliance approval. Hand-crafted test files miss relationships and break at scale. POCs stall while access is negotiated.

**ai-data-platform** is a local-first tool that turns a schema declaration or a small sample into FK-safe, realistic synthetic data in minutes — with automated quality scoring, semantic models, SQL analytics, and AI-driven workflows. No cloud account. No PII exposure. Works in retail, healthcare, finance, and any other domain without custom code.


| Without ADP                                  | With ADP                                         |
| -------------------------------------------- | ------------------------------------------------ |
| Wait 2–6 weeks for production data access    | Generate 50k rows in under a minute              |
| Hand-write fake CSVs that break FK integrity | FK-safe, zero-orphan data at any volume          |
| Rebuild test data after every schema change  | Re-run `apply-spec` or `scan` → regenerate       |
| Demo dashboards on empty tables              | Realistic distributions from day one             |
| Share production exports (PII risk)          | Synthetic data — no real PII leaves your machine |




### Acceleration timeline


| Phase                     | Traditional                        | With ai-data-platform                             |
| ------------------------- | ---------------------------------- | ------------------------------------------------- |
| Get representative data   | 2–6 weeks                          | 5–10 minutes                                      |
| Validate data quality     | Manual spot-checks                 | Automated score + report                          |
| Build semantic layer      | Weeks of hand-written YAML         | Auto-detected facts/dims/measures                 |
| Demo to stakeholders      | Empty charts or risky prod samples | Realistic KPIs on synthetic data                  |
| Onboard a new team member | "Ask someone for the test dump"    | `adp init && adp apply-spec && adp generate-data` |




### Works in any domain — zero customization

There is no `if domain == "healthcare"` in the codebase. Retail orders, patient admissions, bank transactions, factory work orders, and telecom CDRs are all just tables, keys, categories, amounts, and dates.


| Domain                  | What you build faster                                      | Validated example                                                                                                               |
| ----------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Retail / E-commerce** | Sales performance, YoY trends, category mix                | [retail-ecommerce](examples/retail-ecommerce/) — 3 years of orders → Snowflake |
| **Healthcare**          | Patient analytics, admission workflows, compliance testing | [healthcare-claims](https://github.com/Yogi776/data-generation-sdk/tree/main/healthcare-claims) — 5+ tables, temporal/hierarchy |
| **Finance / Banking**   | Risk scoring, transaction monitoring, regulatory reporting | FK-safe account → transaction chains                                                                                            |
| **SaaS / CRM**          | Customer 360, churn models, sales pipelines                | Same pattern as retail — connect CSV/DB samples and profile                                                                       |
| **Manufacturing / IoT** | Supply chain dashboards, work-order tracking               | Parent-child BOM relationships                                                                                                  |
| **Any new vertical**    | POC before production access is granted                    | Cold-start from `spec.yaml` — no sample data needed                                                                             |


---



## End-to-end — what you get

One project, one flow, five tangible deliverables:

```
  YOUR INPUT                    ADP PIPELINE                      YOUR OUTPUT
  ──────────                    ────────────                      ───────────

  spec.yaml          ──▶  apply-spec  ──▶  catalog + profiles
  or CSV/DB sample   ──▶  scan/profile ──▶  learned distributions
                              │
                              ▼
                         generate-data
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         output/         quality.md      semantic model
    (parquet/csv/      (score +          (Cube.js YAML
     duckdb files)      evidence)         for BI tools)
              │
              ▼
         explore / ui / sql
    (query, dashboard KPIs,
     natural-language analytics)
```


| Deliverable         | What it is                                                       | Who uses it                       |
| ------------------- | ---------------------------------------------------------------- | --------------------------------- |
| `output/`           | FK-safe synthetic tables (Parquet, CSV, DuckDB, or SQL)          | Engineers, QA, ML pipelines       |
| `quality.md`        | Weighted score (0–100) with per-check pass/fail evidence         | QA, data engineers, compliance    |
| **Semantic model**  | Auto-detected facts, dimensions, measures → Cube.js YAML         | BI developers, analytics teams    |
| **Data dictionary** | Markdown documentation of every table and column                 | Onboarding, documentation, audits |
| **SQL analytics**   | Query generated data in DuckDB; NL-to-SQL for business questions | Analysts, product managers, demos |


**A complete example:** A product manager describes a retail dataset → agent applies a spec → 50k rows generated → quality score 100/100 → revenue-by-city query returns realistic KPIs → stakeholder demo ready in one session. No production data touched.

Full walkthrough: [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md)

---



## Who it's for


| Persona                          | Your problem                                 | What you do                                               | What you get (in minutes)                                         |
| -------------------------------- | -------------------------------------------- | --------------------------------------------------------- | ----------------------------------------------------------------- |
| **Data engineer**                | Weeks waiting for masked prod exports        | `connect` → `scan` → `profile` → `generate-data`          | FK-safe test data at any volume, CI-reproducible with `--seed 42` |
| **Product / solution architect** | Can't demo until prod access is approved     | `apply-spec spec.yaml` → `generate-data`                  | Working dataset from a design doc — no sample files needed        |
| **Analytics / BI developer**     | Dashboards built on empty or fake data       | `generate-data` → `semantic-model` → `explore sql`        | Realistic data + Cube.js layer + queryable KPIs                   |
| **QA / test engineer**           | Hand-crafted CSVs break FK integrity         | `generate-data` → `quality-check`                         | Scored report with 0 orphans guaranteed                           |
| **ML engineer**                  | Not enough labeled data to train or evaluate | `profile` (learn shapes) → `generate-data --rows 1000000` | 1M rows preserving statistical distributions                      |
| **AI agent user**                | Agent has nothing to work with in the IDE    | MCP: "generate 10k rows and run quality check"            | Full pipeline driven by natural language in Cursor/Claude         |
| **Consultant / SI**              | Every client engagement starts from zero     | Same tool, swap `spec.yaml` per domain                    | Retail Monday, healthcare Tuesday — no custom code                |


**Not sure where to start?**


| If you are…                   | Start here                                                            | Time   |
| ----------------------------- | --------------------------------------------------------------------- | ------ |
| Non-technical / business user | Ask your AI agent (Path C) or read [USE-CASES.md](docs/USE-CASES.md)  | 3 min  |
| Have a schema but no data     | [Path A](#path-a--no-data-needed-5-min) — `apply-spec`                | 5 min  |
| Have CSV or database samples  | [Path B](#path-b--learn-from-sample-data-10-min) — `connect` → `scan` | 10 min |
| Want the full tutorial        | [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md)                    | 15 min |


---



## How it works

Three ways in. Same pipeline. Same validated output.

```mermaid
flowchart TD
  subgraph paths [Choose your path]
    Q1{Have sample data?}
    Q1 -->|No| PathA["Path A: spec.yaml\napply-spec → generate"]
    Q1 -->|Yes| PathB["Path B: learn from data\nconnect → scan → profile → generate"]
    Q1 -->|AI IDE| PathC["Path C: MCP\nCursor / Claude / Windsurf"]
  end

  PathA --> Pipeline
  PathB --> Pipeline
  PathC --> Pipeline

  subgraph Pipeline [Generation pipeline]
    Gen[FK-safe generator]
    QC[quality-check]
    Gen --> QC
  end

  QC --> Out[output/ files]

  Out --> Next[semantic-model · explore sql · ui · docs]
```



**Five steps, plain language:**


| Step            | What happens                                                          | You see                                                |
| --------------- | --------------------------------------------------------------------- | ------------------------------------------------------ |
| 1. **Define**   | Declare your schema (`spec.yaml`) or connect your sample data         | Tables, columns, and relationships in the catalog      |
| 2. **Learn**    | Engine profiles distributions, detects keys, flags PII                | Statistics per column — means, categories, null ratios |
| 3. **Generate** | FK-safe synthetic data at any volume, seeded for reproducibility      | Files in `output/` — one per table                     |
| 4. **Validate** | Auto-derived quality checks run against your metadata                 | Score out of 100 with per-check evidence               |
| 5. **Use**      | Query with SQL, build semantic models, browse in UI, or drive from AI | KPIs, dashboards, data dictionaries, insights          |


Full internals: [docs/USER-FLOW.md](docs/USER-FLOW.md) · Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---



## Get started



### Install

```bash
pip install 'ai-data-platform[all]'      # everything (recommended)
pip install 'ai-data-platform[mcp]'       # MCP only (add to existing install)
pip install 'ai-data-platform[postgres]'  # PostgreSQL connector
```

Requires Python 3.11+.

### Install via Homebrew (macOS)

```bash
brew tap yogi776/tap
brew install ai-data-platform
```

After installation `adp` is available everywhere in your terminal.

```bash
adp version        # verify
adp --help         # see all commands
adp mcp-server --help
```

**Upgrade:** `brew upgrade ai-data-platform`  
**Remove:** `brew uninstall ai-data-platform`  
**Verify:** `which adp && adp version`

> The formula installs all optional extras (`[all]`), including MCP server support.
> Requires macOS (Apple Silicon or Intel) with Python 3.11+ via Homebrew's `python@3.12`.
> For full MCP client setup (Cursor, Claude Desktop, etc.), see the [MCP Guide](docs/MCP-GUIDE.md).

**Troubleshooting:** If `adp` is not found after install, start a new terminal session or run `brew link --overwrite ai-data-platform`. If the issue persists, add Homebrew's bin to your PATH:
```bash
echo 'export PATH="$(brew --prefix)/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

### Path A — no data needed (~5 min)

You have a design doc or schema in mind. No sample files required.

```bash
mkdir demo && cd demo
adp init --name demo
adp apply-spec path/to/spec.yaml       # see healthcare-claims (GitHub) or benchmarks/fixtures/
adp generate-data --rows 50000 --output parquet
adp quality-check --report quality.md
# Optional: push to Snowflake / BigQuery / Postgres (pip install 'ai-data-platform[load]')
# adp load --destination snowflake_dev
```

**You get:** `output/*.parquet` + `quality.md` with score 100/100. See [docs/LOAD.md](docs/LOAD.md) for warehouse export.

### Path B — learn from sample data (~10 min)

You have CSV, Parquet, DuckDB, PostgreSQL, or MySQL samples.

```bash
mkdir demo && cd demo
adp init --name demo
adp connect --name my-db --type csv --path ./data
adp scan && adp profile
adp generate-data --rows 50000 --output parquet
adp quality-check
```

**You get:** Data that mirrors your sample's distributions, scaled to 50k rows.

### Path C — drive from Cursor / Claude (~3 min)

```bash
pip install 'ai-data-platform[mcp]'
cd my-project && adp init && adp setup-agent
```

MCP works with any client (Claude, Cursor, Windsurf, VS Code). Cursor users also get auto-installed agent skills via `adp init`.

Add `.cursor/mcp.json` next to your `adp.yaml` (or use `adp init` to auto-write):

```json
{"mcpServers": {"adp": {"command": "adp", "args": ["mcp-server"]}}}
```

Open the project folder as your workspace, reload MCP, then ask:

> "Apply the healthcare spec and generate 10k rows. Run a quality check and show me the first 10 rows."

**You get:** Agent reports quality score, shows sample rows, files land in `output/`.

**Runnable walkthrough with expected output at every step:** [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md)

**All 16 use cases:** [docs/USE-CASES.md](docs/USE-CASES.md)

---



## Key capabilities


| Capability             | CLI                        | MCP tool                          | What it does                                             |
| ---------------------- | -------------------------- | --------------------------------- | -------------------------------------------------------- |
| Declarative generation | `adp apply-spec`           | `apply_spec`                      | Generate from `spec.yaml` — no sample data               |
| Learn from samples     | `adp scan` + `adp profile` | `scan_sources` + `profile_source` | Discover schema and distributions                        |
| FK-safe generation     | `adp generate-data`        | `generate_synthetic_data`         | Seeded, deterministic, zero orphans                      |
| Quality validation     | `adp quality-check`        | `run_quality_check`               | Weighted score with per-check evidence                   |
| SQL analytics          | `adp explore sql`          | `execute_sql`                     | Query generated data in DuckDB                           |
| Semantic models        | `adp semantic-model`       | `create_semantic_model`           | Auto-detect facts, dims, measures → Cube.js YAML         |
| Natural language SQL   | `adp sql`                  | `generate_sql`                    | NL → read-only SELECT (PII-safe)                         |
| Data dictionary        | `adp docs`                 | `generate_docs`                   | Markdown catalog documentation                           |
| Web console            | `adp ui`                   | —                                 | Browse at [http://127.0.0.1:8765](http://127.0.0.1:8765) |
| AI spec drafting       | —                          | `propose_spec`                    | LLM drafts `spec.yaml` from plain language               |


One backend (`ADPClient`), four interfaces: **CLI · SDK · Web UI · MCP**. Same logic everywhere.

```python
from ai_data_platform import ADPClient

client = ADPClient(".")
client.apply_spec("spec.yaml")
result = client.generate_data(rows=50_000, output_format="parquet")
print(client.quality_check()["quality_score"])   # → 100.0
```

---



## Examples

One walkthrough project — [retail-ecommerce](examples/retail-ecommerce/): **sales performance analysis** with 3 years of order history, generate parquet, `adp load` to Snowflake, and ready-made KPI SQL.

For spec-only generation (no sample data), see [healthcare-claims](https://github.com/Yogi776/data-generation-sdk/tree/main/healthcare-claims) or `benchmarks/fixtures/seasonal-retail-spec.yaml`.


---



## Configuration

**Data sources** (`adp.yaml`):

```yaml
sources:
  - name: csv_files
    type: csv
    path: ./data
  - name: postgres_prod
    type: postgres
    dsn: "postgresql+psycopg://user:${PGPASSWORD}@host:5432/shop"
    schema: public
```

Secrets use `${ENV_VAR}` interpolation — plaintext passwords are rejected.

**AI provider** (for NL-to-SQL and `propose_spec`):

```yaml
model_provider:
  provider: minimax          # minimax | openai | anthropic | gemini | local
  api_key_env: MINIMAX_API_KEY
```

`provider: local` runs fully offline without LLM calls.

**Declarative spec** (`spec.yaml`) — see [docs/SPEC-REFERENCE.md](docs/SPEC-REFERENCE.md):

```yaml
version: 1
tables:
  - name: dim_customer
    columns:
      - {name: customer_id, type: uuid, primary_key: true}
      - {name: gender, type: string, values: {Male: 48, Female: 50, Other: 2}}
      - {name: age, type: int, min: 18, max: 85}
      - {name: signup_date, type: date, start: 2020-01-01, end: 2026-01-01}
```

---



## Documentation


| Guide                                              | What it covers                                                    |
| -------------------------------------------------- | ----------------------------------------------------------------- |
| [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) | Runnable E2E walkthrough — Paths A, B, C, D with expected outputs |
| [docs/USE-CASES.md](docs/USE-CASES.md)             | All 16 use cases — goal, commands, example, expected outcome      |
| [docs/SPEC-REFERENCE.md](docs/SPEC-REFERENCE.md)   | Complete `spec.yaml` language reference                           |
| [docs/MCP-GUIDE.md](docs/MCP-GUIDE.md)             | All 25 MCP tools, agent flows, IDE setup                          |
| [docs/AGENT-FLOW.md](docs/AGENT-FLOW.md)           | Guided agent workflows (intake → KPI validation)                  |
| [docs/USER-FLOW.md](docs/USER-FLOW.md)             | Step-by-step internals for each CLI stage                         |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)       | Design principles, pipeline detail, extension points              |
| [LOCAL-SETUP.md](LOCAL-SETUP.md)                   | macOS dev install and MCP setup                                   |


---

## Benchmarks

Performance benchmarks are in `benchmarks/bench_generation.py`. Run them with Python 3.11+:

```bash
# Smoke test — 100K rows
python benchmarks/bench_generation.py --rows 100000

# Full benchmark — 10M rows per table (3 tables, 30M total rows)
python benchmarks/bench_generation.py \
  --rows 10000000 \
  --rows-per-table "fact_orders=10000000,fact_payments=10000000,fact_shipments=10000000"
```

### Benchmark: Seasonal-Retail Spec · 10M rows/table · Parquet · 1 worker

Generated July 2026 on an 8-core machine.

| Metric | Value |
|---|---|
| **Total rows** | 30,000,000 (10M × 3 tables) |
| **Wall time** | 2 min 55 s |
| **Throughput** | 171,070 rows/s |
| **Peak RSS** | 2,004 MB |
| **Output size** | 2,355 MB (compressed Parquet) |
| **Quality score** | 100/100 ✓ (27/27 checks passed) |
| **Seasonality score** | 100/100 ✓ (4/4 checks passed) |
| **Heuristic memory vs actual** | 3,020 MB est vs 2,004 MB actual (−34%) |

Per-table breakdown:

| Table | Rows | Output | Gen time |
|---|---|---|---|
| `fact_orders` | 10M | 552.8 MB | ~50s |
| `fact_payments` | 10M | 931.6 MB | ~53s |
| `fact_shipments` | 10M | 870.6 MB | ~53s |

#### Bottleneck identified

The execution planner's complexity analyzer correctly flags **GIL-bound Python string samplers** as the thread-scaling ceiling:

```
⚠ fact_orders: 2 per-row Python string sampler(s) (order_id, order_ts_season)
  are GIL-bound and cap thread scaling at scale
  (Phase 3: vectorize).
```

`uuid` and `seasonal_date` samplers are the affected types — they construct strings per-row in Python. Vectorizing these (Phase 3 roadmap) is the single highest-leverage optimization for multi-worker throughput.

#### Memory model accuracy

The static memory estimator (heuristic) predicted 3,020 MB while actual peak RSS was 2,004 MB — a **−34% overestimate**. The `OVERHEAD=2.0` factor in `memory_estimator.py` is conservative; the engine's chunked execution is more memory-efficient than modeled. The estimator correctly flagged the large-table risk but the real system handles it better than the static bound.

#### Scaling ladder (observed)

| Rows/table | Total rows | Wall time | Throughput | Peak RSS |
|---|---|---|---|---|
| 100K | 300K | 1.2 s | 121K rows/s | 119 MB |
| 10M | 30M | 175 s | 171K rows/s | 2,004 MB |

Throughput scales from 121K → 171K rows/s as the system warms up (JIT, OS caches), confirming vectorized numeric generation is not the bottleneck at this scale.

### Output format comparison

Seasonal-retail spec · 5M rows/table · 15M total rows · 1 worker · July 2026.

```bash
# Compare formats at 5M rows/table
python benchmarks/bench_generation.py \
  --rows 5000000 \
  --format csv \
  --rows-per-table "fact_orders=5000000,fact_payments=5000000,fact_shipments=5000000"

python benchmarks/bench_generation.py \
  --rows 5000000 \
  --format parquet \
  --rows-per-table "fact_orders=5000000,fact_payments=5000000,fact_shipments=5000000"

python benchmarks/bench_generation.py \
  --rows 5000000 \
  --format duckdb \
  --rows-per-table "fact_orders=5000000,fact_payments=5000000,fact_shipments=5000000"
```

#### Generation benchmark (5M rows/table)

| Format | Wall time | Throughput | Output size | Quality score |
|---|---|---|---|---|
| **CSV** | **102.3 s** | **146,656 rows/s** | 1,859.7 MB | 100/100 ✓ |
| **Parquet** | 110.2 s | 136,083 rows/s | **1,176.9 MB** | 100/100 ✓ |
| **DuckDB** | 145.7 s | 102,954 rows/s | 2,223.0 MB | N/A* |

\* DuckDB writes a single `generated.duckdb` file; quality/seasonality checks currently expect CSV or Parquet on disk.

#### Micro-benchmark (1M rows · generate + read + aggregate)

| Format | Generate | Read | Aggregate | File size |
|---|---|---|---|---|
| CSV | 12.7 s | 0.0 s | 0.1 s | 128 MB |
| **Parquet** | **12.0 s** | **0.0 s** | **0.1 s** | 121 MB |
| DuckDB | 12.7 s | 0.1 s | 0.1 s | **74 MB** |

#### Recommendations

| Use case | Best format | Why |
|---|---|---|
| Fastest generation | **CSV** | ~8% faster wall time; no columnar encoding overhead |
| Storage efficiency | **Parquet** | 37% smaller than CSV; columnar + ZSTD compression |
| In-database analytics | **DuckDB** | Smallest on-disk footprint; native SQL; zero-copy reads |
| ML / feature stores | **Parquet** | Industry standard; column pruning; cross-platform |
| Demo / CSV-first pipelines | **CSV** | Universal compatibility; fastest write path |

---

## Product & pricing

Commercial packaging and roadmap (draft):

- [Market research](docs/MARKET-RESEARCH.md) — why buyers pay, positioning, target customers, revenue model
- [Data marketplace](docs/DATA-MARKETPLACE.md) — sell synthetic data directly; feasibility and launch plan
- [Data store SKUs](docs/DATA-STORE-SKUS.md) — first 5 product listings ($19–$299)
- [Product roadmap](docs/PRODUCT-ROADMAP.md) — what to sell now, build next, and target customers
- [Pricing](docs/PRICING.md) — tier packaging, vertical SKUs, and services
- [Outbound templates](docs/OUTBOUND-TEMPLATES.md) — email templates for first design partners
- [Dataset license](docs/templates/DATASET-LICENSE.md) — commercial license template for data store

---

## Development

```bash
git clone git@github.com:Yogi776/data-generation-sdk.git
cd data-generation-sdk
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,all]"

pytest && ruff check . && mypy src
```

---



## License

Apache-2.0 — see [LICENSE](./LICENSE).