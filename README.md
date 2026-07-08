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
| **Retail / E-commerce** | Sales dashboards, fraud models, recommendation engines     | [retail-ecommerce](examples/retail-ecommerce/) — 4 tables, 100/100                                                              |
| **Healthcare**          | Patient analytics, admission workflows, compliance testing | [healthcare-claims](https://github.com/Yogi776/data-generation-sdk/tree/main/healthcare-claims) — 5+ tables, temporal/hierarchy |
| **Finance / Banking**   | Risk scoring, transaction monitoring, regulatory reporting | FK-safe account → transaction chains                                                                                            |
| **SaaS / CRM**          | Customer 360, churn models, sales pipelines                | [customer-transaction](examples/customer-transaction/) — 98 columns, 100/100                                                    |
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
adp apply-spec path/to/spec.yaml       # see examples/customer-transaction, healthcare-claims (GitHub)
adp generate-data --rows 50000 --output parquet
adp quality-check --report quality.md
```

**You get:** `output/*.parquet` + `quality.md` with score 100/100.

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


| Example                                                                                         | Path     | Tables    | Best for                         |
| ----------------------------------------------------------------------------------------------- | -------- | --------- | -------------------------------- |
| [customer-transaction](examples/customer-transaction/)                                          | A or B   | 2 (+ KYC) | Full 98-column e-commerce model  |
| [retail-ecommerce](examples/retail-ecommerce/)                                                  | B — CSV  | 4         | Retail star schema, 32/32 checks |
| [healthcare-claims](https://github.com/Yogi776/data-generation-sdk/tree/main/healthcare-claims) | A — spec | 5+        | Temporal rules, hierarchies      |


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