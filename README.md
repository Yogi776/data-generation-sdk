# ai-data-platform

**Local-first AI data platform for synthetic data generation.**

Connect sources, build a metadata catalog, profile your data, generate realistic FK-safe synthetic data, build semantic models, and query in natural language — all driven by MCP for Claude, Cursor, Windsurf, and VS Code.

```
pip install ai-data-platform
```

**Requires Python 3.11+**

---

## Architecture

```mermaid
flowchart TB
    subgraph Interfaces["Interfaces"]
        CLI["CLI (Typer, adp)"]
        API["REST API (FastAPI)"]
        UI["Web UI (static)"]
        MCP["MCP (stdio)"]
    end

    ADP["ADPClient (sdk.py)"]

    subgraph Modules
        CONNECT["Connectors (CSV, Parquet, DuckDB, PostgreSQL, MySQL)"]
        META["Metadata (Catalog: SQLite + SQLAlchemy)"]
        PROF["Profiler (Stats, PII, PK/FK inference)"]
        GEN["Generator (Plan IR, FK-safe, seeded)"]
        QUAL["Quality (derived checks + score)"]
        SEM["Semantic (Fact/Dim to Cube YAML)"]
        SQL["SQL Assistant (NL to SQL, guarded)"]
        DOCS["Docs (Data Dictionary)"]
    end

    Interfaces --> ADP
    ADP --> Modules
    CONNECT -->["CSV, Parquet, DuckDB, PostgreSQL, MySQL"]
    GEN -->["CSV, Parquet, DuckDB, SQL"]

    style Interfaces fill:#1a1a2e,stroke:#e94560,color:#eee
    style ADP fill:#16213e,stroke:#0f3460,color:#eee
    style Modules fill:#0f3460,stroke:#e94560,color:#eee
```

**Design principles:**
- **One backend, many faces** — CLI, API, UI, and MCP all call the same `ADPClient`
- **Metadata-driven** — samplers, checks, and models derive from your catalog; no domain hardcoding
- **Plan IR** — generation compiles to a versioned JSON plan, decoupled from execution
- **Deterministic** — same catalog + seed = byte-identical datasets every time
- **Safe by design** — budgeted sampling, SELECT-only SQL guard, PII never sent to LLMs, writes confined to the project directory

---

## How It Works

```mermaid
flowchart TD
    START(("User"))
    PATH_A["Config-only: adp apply-spec spec.yaml"]
    PATH_B["Learn from data: adp scan + adp profile"]

    START --> PATH_A
    START --> PATH_B

    SPEC["spec.yaml: tables, columns, types, PKs, weights, ranges, FKs"]
    APPLY["adp apply-spec: parses spec to catalog, compiles Plan IR"]

    PATH_A --> SPEC --> APPLY

    CONNECT["adp connect: CSV, Parquet, DuckDB, PostgreSQL, MySQL"]
    SCAN["adp scan: discovers tables, columns, FK candidates"]
    PROFILE["adp profile: nulls, distributions, PII, PK/FK confidence"]

    PATH_B --> CONNECT --> SCAN --> PROFILE

    APPLY & PROFILE --> CATALOG["Metadata Catalog (SQLite)"]

    CATALOG --> PLAN_IR["Plan IR (JSON, versioned, per-table samplers)"]
    PLAN_IR --> SEEDED["Seeded PRNG (deterministic output)"]

    subgraph SAMPLERS
        SEQ["sequence/uuid for PKs"]
        CAT["weighted choice for categoricals"]
        MONEY["lognormal for money/amounts"]
        COUNT["Poisson floor for counts"]
        DATE["uniform date range for timestamps"]
        EXPR["row-level arithmetic expr"]
    end

    SEEDED --> SAMPLERS --> WRITERS["Writers: CSV, Parquet, DuckDB, SQL"]

    WRITERS --> OUT_DATA["output/ (CSV, Parquet, DuckDB)"]

    WRITERS --> RULES["Rules: unique, not-null, range, accepted-values, FK"]
    RULES --> CHECKS["adp quality-check"]
    CHECKS --> SCORE["Quality Score"]
    SCORE --> REPORT["quality.md"]

    CATALOG --> DETECT["Fact vs Dim detection"]
    DETECT --> MEASURES["Measures: sum, count, avg, min, max"]
    DETECT --> JOIN["Joins from FKs"]
    MEASURES & JOIN --> CUBE["Cube.js YAML: model/cubes.yml"]

    CATALOG --> QUESTION["Natural language question"]
    QUESTION --> GROUNDED["Catalog-grounded prompt (PII-safe)"]
    GROUNDED --> PROVIDER["LLM: MiniMax, OpenAI, Anthropic, Gemini, Local"]
    PROVIDER --> SQL_OUT["SELECT statement (read-only)"]

    OUT_DATA -.-> MCP_SERVER["MCP Server (adp mcp-server)"]
    MCP_SERVER --> TOOLS["11 Tools: apply_spec, generate_synthetic_data, run_quality_check, ..."]
    TOOLS --> AGENTS["Claude, Cursor, Windsurf"]

    style START fill:#e94560,stroke:#fff,color:#fff
    style PATH_A fill:#1a1a2e,stroke:#0f3460,color:#eee
    style PATH_B fill:#1a1a2e,stroke:#0f3460,color:#eee
    style CATALOG fill:#0f3460,stroke:#e94560,color:#eee
    style PLAN_IR fill:#0f3460,stroke:#533483,color:#eee
    style WRITERS fill:#0f3460,stroke:#533483,color:#eee
    style RULES fill:#16213e,stroke:#e94560,color:#eee
    style OUT_DATA fill:#1a1a2e,stroke:#533483,color:#eee
    style MCP_SERVER fill:#1a1a2e,stroke:#533483,color:#eee
```

```mermaid
sequenceDiagram
    participant U as User
    participant CLI
    participant SDK as ADPClient
    participant CAT as Catalog
    participant GEN as Generator
    participant QUAL as Quality

    rect rgb(20, 20, 50)
        Note over U,QUAL: Path A: Config-Only (No Data)
        U->>CLI: adp apply-spec spec.yaml
        CLI->>SDK: apply_spec()
        SDK->>CAT: parse and store catalog
        SDK->>GEN: compile_plan_ir()
        U->>CLI: adp generate-data --rows 50k
        CLI->>SDK: generate_data(rows=50k)
        SDK->>GEN: execute_plan()
        GEN->>U: output written
        U->>CLI: adp quality-check
        CLI->>SDK: run_quality_check()
        SDK->>QUAL: derive and run rules
        QUAL-->>SDK: score + report
    end

    rect rgb(20, 50, 40)
        Note over U,QUAL: Path B: Learn from Data
        U->>CLI: adp connect --type csv
        CLI->>SDK: connect()
        U->>CLI: adp scan
        CLI->>SDK: scan()
        SDK->>CAT: store schema + FKs
        U->>CLI: adp profile
        CLI->>SDK: profile()
        SDK->>CAT: store stats + PII
        U->>CLI: adp generate-data
        CLI->>SDK: generate_data()
        SDK->>GEN: compile + execute
        GEN->>U: generated data
    end

    rect rgb(50, 20, 50)
        Note over U,QUAL: Agent Path: MCP
        U->>AGENTS: "Generate 10k test rows"
        AGENTS->>SDK: generate_synthetic_data(rows=10k)
        SDK->>U: output written
        AGENTS->>SDK: run_quality_check()
        SDK-->>AGENTS: quality score
        AGENTS-->>U: Quality: 98/100
    end

    style U fill:#e94560,stroke:#fff,color:#fff
```

---

## Installation

```bash
pip install ai-data-platform              # core only (csv, parquet, duckdb)
pip install 'ai-data-platform[postgres]'  # PostgreSQL connector
pip install 'ai-data-platform[mysql]'     # MySQL connector
pip install 'ai-data-platform[mcp]'       # MCP server (Claude/Cursor/Windsurf)
pip install 'ai-data-platform[all]'       # all runtime extras
```

| Extra | Included in | Purpose |
|---|---|---|
| `[postgres]` | `[all]` | PostgreSQL connector via psycopg |
| `[mysql]` | `[all]` | MySQL connector via pymysql |
| `[mcp]` | `[all]` | MCP server for AI IDE integrations |
| `[dev]` | - | Testing, linting, type checking, packaging |

---

## Quickstart

```bash
# 1. Initialize a project
mkdir demo && cd demo
adp init --name my-project

# 2. Connect your data source
adp connect --name my-db --type csv --path ./data
#                    --type postgres --dsn "postgresql+psycopg://user:${PASSWORD}@host/db"
#                    --type duckdb  --path ./data.duckdb

# 3. Build the catalog
adp scan                    # discovers tables, columns, FK candidates

# 4. Profile for statistics
adp profile                 # nulls, distributions, PII, PK/FK confidence

# 5. Generate synthetic data
adp generate-data --rows 50000 --output parquet

# 6. Validate quality
adp quality-check --report quality-report.md
```

**No data at all?** Use the declarative spec path:

```bash
adp init --name my-project
adp apply-spec examples/customer-transaction/spec.yaml
adp generate-data --rows 50000
```

---

## Generate without writing code

`adp apply-spec spec.yaml` generates data purely from a YAML declaration - no source data needed. Define tables, columns, distributions, and FKs declaratively:

```yaml
version: 1
tables:
  - name: dim_customer
    columns:
      - name: customer_id
        type: uuid
        primary_key: true
      - name: gender
        type: string
        values: {Male: 48, Female: 50, Other: 2}
      - name: age
        type: int
        min: 18
        max: 85
      - name: signup_date
        type: date
        start: 2020-01-01
        end: 2026-01-01
```

---

## MCP Setup (Cursor, Claude, Windsurf, VS Code)

```bash
pip install 'ai-data-platform[mcp]'
```

Add to your IDE's MCP config file:

**Cursor** (`~/.cursor/mcp.json`) or **Windsurf** (`~/.codeium/windsurf/mcp_config.json`):

```json
{
  "mcpServers": {
    "adp": {
      "command": "adp",
      "args": ["mcp-server", "--project", "/path/to/your/project"]
    }
  }
}
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "adp": {
      "command": "adp",
      "args": ["mcp-server", "--project", "/path/to/your/project"]
    }
  }
}
```

**Claude Code** (CLI):

```bash
claude mcp add adp -- adp mcp-server --project /path/to/your/project
```

### MCP Tools available

| Tool | Description |
|---|---|
| `scan_sources` | Discover schemas and relationships |
| `profile_source` | Profile tables (stats, PII, PK/FK) |
| `generate_synthetic_data` | Generate FK-safe synthetic data |
| `run_quality_check` | Score and validate generated data |
| `search_metadata` | Search catalog for tables/columns |
| `get_table_schema` | Get table column details |
| `generate_sql` | NL to read-only SQL |
| `create_semantic_model` | Build Cube.js semantic model |
| `generate_docs` | Markdown data dictionary |

---

## Python SDK

```python
from ai_data_platform import ADPClient

client = ADPClient(project_path=".")

client.scan()
client.profile()

result = client.generate_data(rows=50_000, output_format="parquet")
print(result)  # {seed, format, tables: {<name>: {rows, path}}}

report = client.quality_check()
print(report["quality_score"])  # e.g. 99.75

model = client.create_semantic_model(fmt="cube")
print(model["rendered"])  # Cube.js YAML
```

---

## Command Reference

| Command | What it does |
|---|---|
| `adp init` | Create adp.yaml and .adp/ catalog directory |
| `adp connect` | Add a data source (csv, parquet, duckdb, postgres, mysql) |
| `adp scan` | Discover tables, columns, and FK candidates |
| `adp profile` | Compute stats, detect PII, confirm PKs/FKs |
| `adp apply-spec` | Register a declarative YAML spec - no source data needed |
| `adp generate-data` | Generate synthetic data (csv / parquet / duckdb / sql) |
| `adp quality-check` | Run auto-derived checks and print weighted quality score |
| `adp semantic-model` | Build a Cube.js or generic semantic model as YAML |
| `adp sql "question"` | Convert natural language to read-only SQL |
| `adp docs` | Generate a Markdown data dictionary |
| `adp tables --search` | Search the catalog |
| `adp ui` | Start the local web console at http://127.0.0.1:8765 |
| `adp mcp-server` | Start the MCP server (stdio) for AI IDE integration |

---

## AI Provider for NL-to-SQL

NL-to-SQL uses a configurable model provider. Set your API key in the environment:

```bash
export MINIMAX_API_KEY=your_key_here    # default
# or
export OPENAI_API_KEY=your_key_here
```

Select the provider in `adp.yaml`:

```yaml
model_provider:
  provider: minimax    # minimax | openai | anthropic | gemini | local
  base_url: https://api.minimax.io/v1   # for minimax / compatible endpoints
  model: MiniMax-Text-01
  api_key_env: MINIMAX_API_KEY
```

`provider: local` runs the pipeline without any LLM calls (offline).

---

## Data Connectors

```yaml
sources:
  - name: csv_files
    type: csv
    path: ./data

  - name: parquet_files
    type: parquet
    path: ./data

  - name: duckdb_file
    type: duckdb
    path: ./warehouse.duckdb

  - name: postgres_prod
    type: postgres
    dsn: "postgresql+psycopg://user:${PGPASSWORD}@host:5432/shop"
    schema: public

  - name: mysql_app
    type: mysql
    dsn: "mysql+pymysql://user:${MYSQL_PASSWORD}@host:3306/app"
```

Secrets use `${ENV_VAR}` interpolation - plaintext secrets in adp.yaml are rejected at load.

---

## Worked Examples

### Retail e-commerce (CSV, 4 tables, 32/32 checks validated)

```bash
cd examples/retail-ecommerce
python make_data.py
adp init --name retail && adp connect --name shop --type csv --path ./data
adp scan && adp profile
adp generate-data --rows 50000 --output parquet
adp quality-check --report quality-report.md
adp semantic-model --format cube --out model/cubes.yml
adp docs && adp ui
```

### Customer + Transaction (declarative spec, 50K rows, 100/100 quality)

```bash
cd examples/customer-transaction
adp apply-spec spec.yaml
adp generate-data --rows 50000 --output parquet
adp quality-check
```

### Healthcare (5 tables, 159 columns, 212 checks, 100/100 quality)

```bash
cd examples/healthcare
adp apply-spec spec.yaml
adp generate-data --rows 50000
adp quality-check
```

---

## Development

```bash
git clone git@github.com:Yogi776/data-generation-sdk.git
cd data-generation-sdk
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,all]"

pytest          # run tests
ruff check .    # lint
mypy src        # type check
```

---

## Publishing

**PyPI Trusted Publishing (OIDC)** - no API tokens needed.

```bash
# Release candidate to TestPyPI
git tag v0.2.0rc1 && git push origin v0.2.0rc1

# Full release to PyPI (triggered by GitHub Release)
# 1. Create release on GitHub -> publishes to PyPI automatically
```

See [`.github/workflows/publish.yml`](./.github/workflows/publish.yml) for the full CI/CD pipeline.

---

## Contributing

Issues and PRs welcome. Ground rules:
- No hardcoded domain logic - everything derives from metadata
- Every PR includes tests
- Secrets never in code or config
- Sign off commits (DCO)

---

## License

Apache-2.0 - see [LICENSE](./LICENSE).
