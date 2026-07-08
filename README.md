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
    subgraph Interfaces["🔌 Interfaces (thin adapters, zero logic)"]
        CLI["CLI<br>Typer<br>`adp`"]
        API["REST API<br>FastAPI"]
        UI["Web UI<br>Static"]
        MCP["MCP<br>stdio"]
    end

    subgraph Core["⚙️ ADPClient (sdk.py — the ONLY backend)"]
        ADP["ADPClient"]
    end

    subgraph Modules["📦 Core Modules"]
        direction TB
        CONNECT["🔗 Connectors<br>CSV · Parquet · DuckDB · PostgreSQL · MySQL<br>+ Registry"]
        META["📋 Metadata<br>Catalog: SQLite + SQLAlchemy<br>Scan · Models"]
        PROF["📊 Profiler<br>Stats · PII · PK/FK inference"]
        GEN["🎲 Generator<br>Plan IR + Samplers<br>FK-safe writers"]
        QUAL["✅ Quality<br>Derived checks + Score"]
        SEM["🧠 Semantic<br>Fact/Dim → Cube YAML"]
        SQL["💬 SQL Assistant<br>NL→SQL · guarded"]
        DOCS["📄 Docs<br>Data Dictionary"]
    end

    subgraph Sources["📥 Sources"]
        CSV["CSV"]
        PARQUET["Parquet"]
        DUCKDB["DuckDB"]
        PG["PostgreSQL"]
        MYSQL["MySQL"]
    end

    subgraph Outputs["📤 Outputs"]
        CSV_OUT["CSV"]
        PARQUET_OUT["Parquet"]
        DUCKDB_OUT["DuckDB"]
        SQL_OUT["SQL"]
    end

    subgraph Providers["🤖 LLM Providers"]
        MINIMAX["MiniMax<br>default"]
        OPENAI["OpenAI"]
        ANTHROPIC["Anthropic"]
        GEMINI["Gemini"]
        STUB["Local Stub"]
    end

    Interfaces --> ADP
    ADP --> Modules
    CONNECT --> Sources
    GEN --> Outputs
    SEM --> Providers
    SQL --> Providers

    style Interfaces fill:#1a1a2e,stroke:#e94560,color:#eee
    style Core fill:#16213e,stroke:#0f3460,color:#eee
    style Modules fill:#0f3460,stroke:#e94560,color:#eee
    style Sources fill:#1a1a2e,stroke:#533483,color:#eee
    style Outputs fill:#1a1a2e,stroke:#533483,color:#eee
    style Providers fill:#1a1a2e,stroke:#533483,color:#eee
```

**Design principles:**
- **One backend, many faces** — CLI, API, UI, and MCP all call the same `ADPClient`
- **Metadata-driven** — samplers, checks, and models derive from your catalog; no domain hardcoding
- **Plan IR** — generation compiles to a versioned JSON plan, decoupled from execution
- **Deterministic** — same catalog + seed ⇒ byte-identical datasets every time
- **Safe by design** — budgeted sampling, SELECT-only SQL guard, PII never sent to LLMs, writes confined to the project directory

---

## How It Works

```mermaid
flowchart TD
    START(["🚀 User Entry Point"])

    subgraph Entry["Choose Your Path"]
        PATH_A["📋 Config-only<br>`adp apply-spec spec.yaml`"]
        PATH_B["🔍 Learn from data<br>`adp scan` → `adp profile`"]
    end

    START --> Entry

    subgraph ConfigPath["⚙️ Config-Only Path (No Data Required)"]
        SPEC["`spec.yaml`<br>tables · columns · types · PKs<br>categorical weights · numeric shapes<br>date ranges · FK joins · expressions"]
        APPLY["`adp apply-spec`<br>parses spec → catalog<br>compiles plan IR"]
    end

    PATH_A --> SPEC --> APPLY

    subgraph DataPath["🔍 Data Learning Path"]
        CONNECT["`adp connect`<br>CSV · Parquet · DuckDB<br>PostgreSQL · MySQL"]
        SCAN["`adp scan`<br>list tables · columns · types<br>infer FK candidates<br>naming conventions"]
        PROFILE["`adp profile`<br>Polars on sampled rows<br>nulls · distributions · PII<br>PK uniqueness · FK inclusion"]
    end

    PATH_B --> CONNECT --> SCAN --> PROFILE

    subgraph Catalog["📋 Metadata Catalog (SQLite)"]
        CT["`sources` — connection configs"]
        TT["`tables` — name · type · row_count"]
        CT2["`columns` — name · type · nullable<br>PII flag · profile stats"]
        REL["`relationships`<br>FK pairs · confidence"]
        QR["`quality_rules`<br>derived from metadata"]
    end

    APPLY & PROFILE --> Catalog
    CT2 -.-"references<br>FKs"-> REL

    subgraph Generation["🎲 Generation Engine"]
        PLAN_IR["📄 Plan IR<br>JSON · versioned<br>per-table samplers<br>FK strategies · seeds"]
        SEEDED["🔄 Seeded PRNG<br>`sha256(seed, table, chunk)`<br>deterministic output"]

        subgraph Samplers["Sampler Registry"]
            SEQ["sequence / uuid<br>for PKs"]
            CAT["weighted choice<br>for categoricals"]
            MONEY["lognormal<br>for money/amounts"]
            COUNT["Poisson floor<br>for counts"]
            DATE["uniform date range<br>for timestamps"]
            HIER["hierarchical<br>values_by mapping"]
            EXPR["row-level<br>arithmetic expr"]
        end

        WRITERS["📤 Writers<br>CSV · Parquet<br>DuckDB · SQL"]
    end

    Catalog --> PLAN_IR --> SEEDED --> Samplers --> WRITERS

    subgraph Quality["✅ Quality Engine"]
        RULES["Rules from metadata<br>unique · not-null · range<br>accepted-values · FK"]
        CHECKS["`adp quality-check`<br>run all rules"]
        SCORE["📊 Quality Score<br>weighted explained score"]
        REPORT["`quality.md`<br>detailed report"]
    end

    WRITERS -.->"generated data"-> RULES
    RULES --> CHECKS --> SCORE --> REPORT

    subgraph Semantic["🧠 Semantic Layer"]
        DETECT["Fact vs Dim detection<br>FK density + measure shape"]
        MEASURES["Measures<br>sum · count · avg · min · max"]
        JOIN["Joins from FKs<br>confirmed relationships"]
        CUBE["Cube.js YAML<br>`model/cubes.yml`"]
    end

    Catalog --> DETECT --> MEASURES & JOIN --> CUBE

    subgraph NL_SQL["💬 NL → SQL"]
        QUESTION["Natural language question"]
        GROUNDED["Catalog-grounded prompt<br>PII-safe (no sample values)"]
        PROVIDER["LLM Provider<br>MiniMax · OpenAI · Anthropic<br>Gemini · Local stub"]
        SQL_OUT["SELECT statement<br>validated read-only"]
    end

    Catalog --> GROUNDED
    QUESTION --> GROUNDED --> PROVIDER --> SQL_OUT

    subgraph Output["📤 Final Outputs"]
        OUT_DATA["`output/` directory<br>CSV · Parquet · DuckDB"]
        OUT_CUBE["`model/cubes.yml`"]
        OUT_DOCS["`docs/`"]
        OUT_QUALITY["`quality.md`"]
    end

    WRITERS --> OUT_DATA
    CUBE --> OUT_CUBE
    REPORT --> OUT_QUALITY

    subgraph Agent["🤖 Agent Integration (MCP)"]
        MCP["MCP Server<br>`adp mcp-server`"]
        TOOLS["11 Tools<br>apply_spec · generate_synthetic_data<br>preview_data · run_quality_check<br>scan · profile · semantic_model<br>sql · docs · ui"]
        CLAUDE["Claude · Cursor · Windsurf"]
    end

    OUT_DATA -.-> MCP
    MCP --> TOOLS --> CLAUDE

    style START fill:#e94560,stroke:#fff,color:#fff
    style Entry fill:#1a1a2e,stroke:#0f3460,color:#eee
    style ConfigPath fill:#1a1a2e,stroke:#0f3460,color:#eee
    style DataPath fill:#1a1a2e,stroke:#0f3460,color:#eee
    style Catalog fill:#0f3460,stroke:#e94560,color:#eee
    style Generation fill:#16213e,stroke:#e94560,color:#eee
    style Quality fill:#16213e,stroke:#e94560,color:#eee
    style Semantic fill:#16213e,stroke:#e94560,color:#eee
    style NL_SQL fill:#16213e,stroke:#e94560,color:#eee
    style Agent fill:#1a1a2e,stroke:#533483,color:#eee
    style Output fill:#1a1a2e,stroke:#533483,color:#eee
    style PLAN_IR fill:#0f3460,stroke:#533483,color:#eee
    style SEEDED fill:#0f3460,stroke:#533483,color:#eee
    style WRITERS fill:#0f3460,stroke:#533483,color:#eee
```

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant CLI as CLI `adp`
    participant SDK as ADPClient
    participant CAT as Catalog
    participant GEN as Generator
    participant QUAL as Quality
    participant OUT as Output

    rect rgb(20, 20, 50)
        Note over U,OUT: Path A: Config-Only (No Data)
        U->>CLI: adp apply-spec spec.yaml
        CLI->>SDK: apply_spec(spec_yaml)
        SDK->>CAT: parse & store catalog
        SDK->>GEN: compile_plan_ir()
        GEN-->>CAT: plan IR
        U->>CLI: adp generate-data --rows 50k
        CLI->>SDK: generate_data(rows=50k)
        SDK->>GEN: execute_plan(plan_ir)
        GEN->>OUT: write parquet/csv
        U->>CLI: adp quality-check
        CLI->>SDK: run_quality_check()
        SDK->>QUAL: derive & run rules
        QUAL-->>SDK: score + report
    end

    rect rgb(20, 50, 40)
        Note over U,OUT: Path B: Learn from Data
        U->>CLI: adp connect --type csv --path ./data
        CLI->>SDK: connect(source_config)
        U->>CLI: adp scan
        CLI->>SDK: scan()
        SDK->>CAT: store schema + FK candidates
        U->>CLI: adp profile
        CLI->>SDK: profile()
        SDK->>CAT: store stats + PII + PK/FK
        U->>CLI: adp generate-data --rows 100k
        CLI->>SDK: generate_data(rows=100k)
        SDK->>GEN: compile + execute
        GEN->>OUT: generated data
    end

    rect rgb(50, 20, 50)
        Note over U,OUT: Agent Path: MCP
        U->>CLAUDE: "Generate 10k test rows"
        CLAUDE->>MCP: apply_spec(spec_yaml)
        MCP->>SDK: apply_spec()
        CLAUDE->>MCP: generate_synthetic_data(rows=10k)
        MCP->>SDK: generate_data(rows=10k)
        SDK->>OUT: write output
        CLAUDE->>MCP: run_quality_check()
        MCP->>SDK: run_quality_check()
        SDK-->>MCP: quality score
        MCP-->>CLAUDE: quality score
        CLAUDE-->>U: ✅ Done! Quality: 98/100
    end

    style U fill:#e94560,stroke:#fff,color:#fff
    style CLAUDE fill:#533483,stroke:#fff,color:#fff
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
| `[dev]` | — | Testing, linting, type checking, packaging |

---

## Quickstart

```bash
# 1. Initialize a project
mkdir demo && cd demo
adp init --name my-project

# 2. Connect your data source
adp connect --name my-db --type csv --path ./data
#                    ── or ──
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

`adp apply-spec spec.yaml` generates data purely from a YAML declaration — no source data needed. Define tables, columns, distributions, and FKs declaratively:

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
| `generate_sql` | NL → read-only SQL |
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
| `adp init` | Create `adp.yaml` and `.adp/` catalog directory |
| `adp connect` | Add a data source (csv, parquet, duckdb, postgres, mysql) |
| `adp scan` | Discover tables, columns, and FK candidates |
| `adp profile` | Compute stats, detect PII, confirm PKs/FKs |
| `adp apply-spec` | Register a declarative YAML spec — no source data needed |
| `adp generate-data` | Generate synthetic data (csv / parquet / duckdb / sql) |
| `adp quality-check` | Run auto-derived checks and print weighted quality score |
| `adp semantic-model` | Build a Cube.js or generic semantic model as YAML |
| `adp sql "question"` | Convert natural language to read-only SQL |
| `adp docs` | Generate a Markdown data dictionary |
| `adp tables --search` | Search the catalog |
| `adp ui` | Start the local web console at `http://127.0.0.1:8765` |
| `adp mcp-server` | Start the MCP server (stdio) for AI IDE integration |

---

## AI Provider for NL→SQL

NL→SQL uses a configurable model provider. Set your API key in the environment:

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
    path: ./data                      # file or directory of CSVs

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

Secrets use `${ENV_VAR}` interpolation — plaintext secrets in `adp.yaml` are rejected at load.

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

Declarative spec at `examples/healthcare/` — no source data needed:

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

**PyPI Trusted Publishing (OIDC)** — no API tokens needed.

```bash
# Release candidate to TestPyPI
git tag v0.2.0rc1 && git push origin v0.2.0rc1

# Full release → PyPI (triggered by GitHub Release)
# 1. Create release on GitHub → publishes to PyPI automatically
```

See [`.github/workflows/publish.yml`](./.github/workflows/publish.yml) for the full CI/CD pipeline.

---

## Contributing

Issues and PRs welcome. Ground rules:
- No hardcoded domain logic — everything derives from metadata
- Every PR includes tests
- Secrets never in code or config
- Sign off commits (DCO)

---

## License

Apache-2.0 — see [LICENSE](./LICENSE).
