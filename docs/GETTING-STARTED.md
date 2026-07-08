# Getting Started

A runnable, copy-paste walkthrough for every entry path. Each step shows the command, the files it creates, and what the output looks like.

---

## 0. Prerequisites

```bash
# Verify Python version (needs 3.11+)
python3 --version

# Install
pip install 'ai-data-platform[all]'

# Verify
adp version
# → ai-data-platform 0.2.1
```

If `adp: command not found`, activate your virtual environment first:

```bash
source /path/to/venv/bin/activate
```

---

## 1. Choose your path

| Situation | Path | Time | Example |
|---|---|---|---|
| No data; you have a design doc or schema in mind | A — spec-only | ~5 min | `healthcare-claims` |
| Have CSV/Parquet/DB samples you want to learn from | B — learn from data | ~10 min | `examples/customer-transaction` |
| Using Cursor, Claude Code, or Windsurf | C — MCP | ~3 min | `cursor-test/` |
| Want to explore generated data with SQL | D — Explorer | after any generate | `adp explore sql` |
| Quality passes but KPIs drift from research targets | E — Calibrate | ~5 min | adjust `values` weights in spec |

All paths end at `output/` with quality-validated synthetic data.

---

## Path A — spec-only (no data needed)

Use this when you have no sample data but know your schema — either from a design doc or by writing `spec.yaml` by hand. The engine generates FK-safe data purely from your declaration.

### Step 1 — Init

```bash
mkdir my-project && cd my-project
adp init --name my-project
```

**Files created:**
```
my-project/
├── adp.yaml          # project config (name, output dir, generation defaults)
└── .adp/             # catalog directory (created on first use)
    └── catalog.db    # SQLite metadata catalog
```

**What success looks like:**

```
Project 'my-project' initialized.
Run `adp apply-spec <spec.yaml>` to define your schema.
```

### Step 2 — Apply a spec

Copy a ready-made spec from the examples:

```bash
# customer-transaction (2 tables + KYC, 98 columns)
cp ../ai-data-platform/examples/customer-transaction/spec.yaml .

# Or get the healthcare-claims spec from the GitHub repo:
# https://github.com/Yogi776/data-generation-sdk/blob/main/healthcare-claims/spec.yaml
```

Or create your own `spec.yaml`. See [SPEC-REFERENCE.md](SPEC-REFERENCE.md) for the full language.

```bash
adp apply-spec spec.yaml
```

**What success looks like:**

```
Applied spec: 3 tables registered.
  - customers        (4 columns, PK: customer_id)
  - products         (3 columns, PK: product_id)
  - transactions     (5 columns, PK: transaction_id, FK: customer_id, product_id)
Catalog updated. Run `adp generate-data` to produce synthetic data.
```

### Step 3 — Generate

```bash
adp generate-data --rows 10000 --output parquet
```

**Files created:**

```
my-project/
├── adp.yaml
├── spec.yaml
└── output/
    ├── customers.parquet
    ├── products.parquet
    └── transactions.parquet
```

**What success looks like:**

```
Generating synthetic data...
  customers   10,000 rows  ████████████████████  100%  0.2s
  products        100 rows  ████████████████████  100%  0.1s
  transactions  10,000 rows  ████████████████████  100%  0.3s

Output: output/ (parquet)
Total: 20,100 rows across 3 tables
Seed: 42  (same seed = byte-identical output)
```

### Step 4 — Quality check

```bash
adp quality-check --report quality.md
```

**What success looks like:**

```
Running quality checks...
  customers         4/4  ✓  (PK unique, not-null, FK intact)
  products          3/3  ✓  (PK unique, not-null)
  transactions      5/5  ✓  (PK unique, not-null, FK: customer_id ✓, product_id ✓)

Quality score: 100/100

Full report: quality.md
```

### Inspect the data

```bash
# Browse the catalog
adp tables
# → customers    (4 cols)  PK: customer_id
# → products     (3 cols)  PK: product_id
# → transactions (5 cols)  PK: transaction_id  FKs: customer_id → customers, product_id → products

# Preview a table (CLI explorer)
adp explore preview transactions --limit 5
# → 5 rows printed as a formatted table

# Or use the web UI
adp ui
# → http://127.0.0.1:8765
```

**Reproduce exactly:**

```bash
# Same data every time with seed 42
adp generate-data --rows 10000 --seed 42

# Different data, same shapes (any other seed)
adp generate-data --rows 10000 --seed 123
```

---

## Path B — learn from sample data

Use this when you have representative data samples (CSVs, Parquet, DuckDB, PostgreSQL, or MySQL). The engine scans your schema, profiles distributions, and generates data that mirrors your real data's shapes and relationships.

### Input quality guide

| Sample size | What you get |
|---|---|
| Headers only (0 rows) | Single-table generation; no distributions learned |
| ~10 rows/table | FK-safe dev data; ~75/100 quality score |
| 100–500 rows/table | Good fidelity; recommended for development |
| 500+ rows/table | Production-quality fidelity; validated 100/100 |

### Step 1 — Init and connect

```bash
cd examples/customer-transaction
adp init --name crm-demo
adp connect --name crm --type csv --path ./data
```

> **Tip:** Put your CSV/Parquet files in a `./data/` folder. Point `--path` at that folder. Each file becomes a table named by its filename.

**Files created:**
```
examples/customer-transaction/
├── adp.yaml          # updated with source
└── data/
    ├── dim_customer.csv
    └── fact_transaction.csv
```

**What success looks like:**

```
Connecting source 'shop' (csv)...
  Found 2 tables: customers, orders
Connection saved to adp.yaml.
```

For PostgreSQL:

```bash
export PGPASSWORD=yourpassword    # or put in .env
adp connect --name prod --type postgres \
  --dsn "postgresql+psycopg://user:${PGPASSWORD}@localhost:5432/shop" \
  --schema public
```

### Step 2 — Scan (discover schema)

```bash
adp scan
```

**What success looks like:**

```
Scanning source 'shop'...
  customers   (4 columns)  FK candidates: none
  orders      (4 columns)  FK: customer_id → customers (confidence 0.95)

Scan complete. 2 tables registered in catalog.
Use `adp profile` to compute statistics.
```

### Step 3 — Profile (learn distributions)

```bash
adp profile
# Optional: --sample-rows 20000 to profile more rows per table
```

**What success looks like:**

```
Profiling 'customers' (847 rows, sampled 847)...
  customer_id   uuid      PK candidate  unique=100%  nulls=0%
  name          string    top: John(4%), Mary(3%), ...  entropy=4.2
  email         string    format: *@example.com  PII suspected (email)
  city          string    top: New York(15%), London(12%), ...

Profiling 'orders' (3,291 rows, sampled 3,291)...
  order_id      uuid      PK candidate  unique=100%  nulls=0%
  customer_id   uuid      FK → customers  verified 100%
  amount        float     mean=$142.50  std=$89.30  nulls=2%
  status        string    Delivered=80%, Processing=12%, Cancelled=8%

PII detected: customers.email (email pattern)
Quality: 100/100  (32 checks)
```

### Step 4 — Generate

```bash
adp generate-data --rows 50000 --output parquet
```

**What success looks like:**

```
Generating synthetic data (learned from profiles)...
  customers   50,000 rows  ████████████████████  100%  0.4s
  orders      50,000 rows  ████████████████████  100%  0.6s

  FK integrity: 0 orphans across all relationships
Output: output/ (parquet)
```

### Step 5 — Quality check

```bash
adp quality-check
```

**What success looks like:**

```
Quality score: 100/100
  customers   4/4  ✓  PK unique, not-null, no duplicates
  orders      4/4  ✓  PK unique, not-null, FK: customer_id → customers ✓
```

---

## Path C — MCP from an AI IDE

Let Cursor, Claude Code, or Windsurf drive the full pipeline. The MCP server auto-discovers your project from the workspace directory — no hardcoded paths needed.

### Step 1 — Install MCP extra

```bash
pip install 'ai-data-platform[mcp]'
```

### Step 2 — Init your project

```bash
mkdir my-ai-project && cd my-ai-project
adp init --name my-ai-project
```

`adp init` auto-writes MCP configs (`.cursor/mcp.json`, `.windsurf/mcp.json`, `.vscode/mcp.json`) and Cursor skills (`.cursor/skills/adp-*`). Run `adp setup-agent` to re-sync or configure Claude.

### Step 3 — Configure the MCP server

If you used `adp init`, skip this step. Otherwise create `.cursor/mcp.json` **next to your `adp.yaml`**:

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

> The server auto-discovers the project from the workspace root (cwd). Optional: `--project ./subdir` to override.

For Claude Code CLI:

```bash
claude mcp add adp -- adp mcp-server
```

### Step 4 — Reload MCP in your IDE

Open the folder containing your `adp.yaml` as the workspace root, then reload MCP (Cursor: Ctrl+Shift+P → "Reload MCP").

### Step 5 — Talk to the agent

Here are exact prompts to try:

**Path A (spec-only):**

> "Apply the customer-transaction spec from `../ai-data-platform/examples/customer-transaction/spec.yaml` and generate 10,000 rows of test data. Run a quality check when done."

The agent will call: `apply_spec` → `generate_synthetic_data` → `run_quality_check`

**Path B (from your data):**

> "Scan my CSV source, profile the tables, and generate 20,000 rows of test data. Run a quality check."

The agent will call: `scan_sources` → `profile_source` → `generate_synthetic_data` → `run_quality_check`

**Inspect what was generated:**

> "Show me the first 10 rows of the customers table and give me a summary of the data quality."

The agent will call: `preview_data` → `run_quality_check`

See [MCP-GUIDE.md](MCP-GUIDE.md) for all 25 available tools and all 4 recommended agent flows.

---

## Path D — Explore post-generation SQL analytics

After any successful `generate-data`, all output files are auto-registered into a DuckDB database. Query your synthetic data with SQL — no manual loading.

> Requires: `generate-data` has run at least once (auto-registers by default).

```bash
# List all registered datasets
adp explore datasets
# → default (1 dataset, 3 tables, 60,100 rows total)

# List tables in a dataset
adp explore tables
# → customers   50,000 rows
# → products       100 rows
# → transactions 50,000 rows

# Run a query
adp explore sql "SELECT city, count(*) as customers FROM customers GROUP BY city ORDER BY customers DESC LIMIT 5"
# → New York    8,421
# → London      7,832
# → Tokyo       6,104
# → Paris       5,987
# → Berlin      5,221

# Get a table description
adp explore describe customers
# → 4 columns: customer_id (uuid, PK), name (string), email (string), city (string)

# Preview rows
adp explore preview transactions --limit 5

# Count rows
adp explore count orders
# → 50,000

# Profile a table (statistics)
adp explore profile orders
# → amount: mean=$142.50, std=$89.30, nulls=2%
# → status: Delivered=80%, Processing=12%, ...

# Explain a query plan
adp explore explain "SELECT * FROM orders WHERE amount > 500"

# Get suggested analytics queries
adp explore suggest transactions
# → Revenue by city?
# → Order count by status?
# → Average order value over time?

# Export query results
adp explore export "SELECT * FROM customers LIMIT 100" top_customers.csv
```

All 13 `adp explore` subcommands mirror equivalent MCP tools (`list_datasets`, `execute_sql`, `preview_table`, etc.). See [MCP-GUIDE.md](MCP-GUIDE.md) for the MCP equivalents.

---

## Path E — Calibrate (when quality passes but KPIs drift)

Use this when `quality-check` scores ≥ 95 but SQL reveals KPI distributions don't match your research targets (e.g., UPI payments generated at 52% but you researched 40%).

### Step 1 — Identify the drift

Run KPI SQL to compare generated vs target distributions:

```bash
adp explore sql "SELECT payment_method, round(count(*)*100.0/sum(count(*)) over(), 1) as pct FROM fact_transaction GROUP BY 1 ORDER BY 2 DESC"
```

Compare each value to your research notes.

### Step 2 — Compute drift

```
drift = |generated_pct - research_pct| / research_pct
```

If any KPI drifts by more than 5%, patch the spec.

### Step 3 — Patch spec weights

Edit `spec.yaml` to adjust `values:` weights for the drifted column. For example, to fix UPI from 52% to 40%:

```yaml
# Before
payment_method:
  values: {UPI: 52, Credit_Card: 22, Debit_Card: 15, Wallet: 8, COD: 3}

# After
payment_method:
  values: {UPI: 40, Credit_Card: 25, Debit_Card: 15, Wallet: 12, COD: 8}
```

### Step 4 — Re-apply and regenerate

```bash
adp apply-spec spec.yaml
adp generate-data --rows 50000 --seed 42   # same seed for byte-identical output
adp quality-check
```

### Step 5 — Re-verify KPIs

```bash
adp explore sql "SELECT payment_method, ... FROM fact_transaction GROUP BY 1"
```

Repeat until all KPIs are within tolerance (default 5%).

> **Tip:** Use `--rows-per-table` to regenerate only specific tables while testing weight changes — faster iteration on large datasets.

---

## Optional next steps

After generating and validating:

```bash
# Build a Cube.js semantic layer
adp semantic-model --format cube --out model/cubes.yml

# Generate a data dictionary
adp docs
# → data-dictionary.md

# Browse via web UI
adp ui
# → http://127.0.0.1:8765

# Query in natural language (needs MINIMAX_API_KEY or OPENAI_API_KEY)
adp sql "revenue by city last quarter"
# → SELECT city, sum(amount) FROM orders WHERE ... GROUP BY city
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `adp: command not found` | Activate your virtual environment: `source venv/bin/activate` |
| `NoAdpYamlError` | Run `adp init` first in your project directory |
| `Connection refused` for Postgres/MySQL | Check credentials; use `${ENV_VAR}` in DSN; verify DB is reachable |
| `SQLite on network mount is slow` | Set `export ADP_CATALOG_DIR=~/.adp-catalogs` to move catalog to local disk |
| `pip install` fails | Ensure Python 3.11+: `python3 --version`; use `pip install --upgrade pip` |
| MCP server not discovered in Cursor | Ensure `.cursor/mcp.json` is **next to your `adp.yaml`**, not in `~/.cursor/` |
| Quality score < 100 | Run `adp profile` with more rows; check FK relationships are detected; see quality-report.md for failing checks |

For full internals, see [USER-FLOW.md](USER-FLOW.md). For extension points, see [ARCHITECTURE.md](ARCHITECTURE.md).
