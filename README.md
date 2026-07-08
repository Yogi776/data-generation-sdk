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
graph TB
    subgraph Interfaces["Interfaces"]
        CLI["CLI (Typer, adp)"]
        API["REST API (FastAPI)"]
        UI["Web UI (static)"]
        MCP["MCP (stdio)"]
    end

    ADP["ADPClient (sdk.py)"]

    subgraph Modules
        CONNECT["Connectors"]
        META["Metadata"]
        PROF["Profiler"]
        GEN["Generator"]
        QUAL["Quality"]
        SEM["Semantic"]
        SQL["SQL Assistant"]
        DOCS["Docs"]
    end

    Interfaces --> ADP
    ADP --> Modules
    CONNECT -->|"CSV Parquet DuckDB PG MySQL"|Modules
    GEN -->|"CSV Parquet DuckDB SQL"|Modules
```

**Design principles:**
- **One backend, many faces** — CLI, API, UI, and MCP all call the same `ADPClient`
- **Metadata-driven** — samplers, checks, and models derive from your catalog; no domain hardcoding
- **Plan IR** — generation compiles to a versioned JSON plan, decoupled from execution
- **Deterministic** — same catalog + seed = byte-identical datasets every time
- **Safe by design** — budgeted sampling, SELECT-only SQL guard, PII never sent to LLMs

---

## How It Works

```mermaid
graph TD
    START(("User"))

    PATH_A["Config-only: adp apply-spec spec.yaml"]
    PATH_B["Learn from data: adp scan + adp profile"]

    START --> PATH_A
    START --> PATH_B

    SPEC["spec.yaml"]
    APPLY["adp apply-spec"]

    PATH_A --> SPEC --> APPLY

    CONNECT["adp connect"]
    SCAN["adp scan"]
    PROFILE["adp profile"]

    PATH_B --> CONNECT --> SCAN --> PROFILE

    APPLY & PROFILE --> CATALOG["Metadata Catalog"]

    CATALOG --> PLAN_IR["Plan IR"]
    PLAN_IR --> SEEDED["Seeded PRNG"]

    SEQ["sequence/uuid"]
    CAT["weighted choice"]
    MONEY["lognormal"]
    COUNT["Poisson floor"]
    DATE["uniform date range"]
    EXPR["arithmetic expr"]

    SEEDED --> SEQ
    SEEDED --> CAT
    SEEDED --> MONEY
    SEEDED --> COUNT
    SEEDED --> DATE
    SEEDED --> EXPR

    SEQ & CAT & MONEY & COUNT & DATE & EXPR --> WRITERS["Writers"]

    WRITERS --> OUT_DATA["output/"]

    WRITERS --> RULES["Rules"]
    RULES --> CHECKS["adp quality-check"]
    CHECKS --> REPORT["quality.md"]

    CATALOG --> DETECT["Fact vs Dim"]
    DETECT --> MEASURES["Measures"]
    DETECT --> JOIN["Joins"]
    MEASURES & JOIN --> CUBE["Cube.js YAML"]

    CATALOG --> QUESTION["NL question"]
    QUESTION --> GROUNDED["PII-safe prompt"]
    GROUNDED --> PROVIDER["LLM"]
    PROVIDER --> SQL_OUT["SELECT"]

    OUT_DATA -.-> MCP["MCP Server"]
    MCP --> TOOLS["11 Tools"]
    TOOLS --> AGENTS["Claude, Cursor, Windsurf"]

    START fill:#e94560
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
        Note over U,QUAL: Path A: Config-Only
        U->>CLI: adp apply-spec spec.yaml
        CLI->>SDK: apply_spec()
        U->>CLI: adp generate-data --rows 50k
        CLI->>SDK: generate_data()
        SDK->>GEN: execute_plan()
        GEN->>U: output written
        U->>CLI: adp quality-check
        CLI->>SDK: run_quality_check()
        SDK->>QUAL: derive and run rules
        QUAL-->>SDK: score + report
    end

    rect rgb(20, 50, 40)
        Note over U,QUAL: Path B: Learn from Data
        U->>CLI: adp connect
        CLI->>SDK: connect()
        U->>CLI: adp scan
        CLI->>SDK: scan()
        U->>CLI: adp profile
        CLI->>SDK: profile()
        U->>CLI: adp generate-data
        CLI->>SDK: generate_data()
        SDK->>GEN: execute_plan()
        GEN->>U: generated data
    end

    rect rgb(50, 20, 50)
        Note over U,QUAL: Agent Path
        U->>AGENTS: Generate 10k rows
        AGENTS->>SDK: generate_synthetic_data()
        SDK->>U: output written
        AGENTS->>SDK: run_quality_check()
        SDK-->>AGENTS: quality score
    end
```

---

## Installation

```bash
pip install ai-data-platform              # core only
pip install 'ai-data-platform[postgres]'  # PostgreSQL
pip install 'ai-data-platform[mysql]'     # MySQL
pip install 'ai-data-platform[mcp]'       # MCP server
pip install 'ai-data-platform[all]'       # all extras
```

| Extra | Included in | Purpose |
|---|---|---|
| `[postgres]` | `[all]` | PostgreSQL via psycopg |
| `[mysql]` | `[all]` | MySQL via pymysql |
| `[mcp]` | `[all]` | MCP for AI IDE integrations |
| `[dev]` | - | Testing, linting, type checking |

---

## Quickstart

```bash
# 1. Initialize a project
mkdir demo && cd demo
adp init --name my-project

# 2. Connect your data source
adp connect --name my-db --type csv --path ./data

# 3. Build the catalog
adp scan

# 4. Profile for statistics
adp profile

# 5. Generate synthetic data
adp generate-data --rows 50000 --output parquet

# 6. Validate quality
adp quality-check --report quality-report.md
```

**No data at all?**

```bash
adp init --name my-project
adp apply-spec examples/customer-transaction/spec.yaml
adp generate-data --rows 50000
```

---

## Generate without writing code

`adp apply-spec spec.yaml` generates data from a YAML declaration:

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

Add to your IDE MCP config:

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

Claude Code CLI:

```bash
claude mcp add adp -- adp mcp-server --project /path/to/your/project
```

### MCP Tools

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
print(result)

report = client.quality_check()
print(report["quality_score"])

model = client.create_semantic_model(fmt="cube")
print(model["rendered"])
```

---

## Command Reference

| Command | What it does |
|---|---|
| `adp init` | Create adp.yaml and .adp/ catalog |
| `adp connect` | Add a data source |
| `adp scan` | Discover tables, columns, FK candidates |
| `adp profile` | Compute stats, detect PII, confirm PKs/FKs |
| `adp apply-spec` | Register a declarative YAML spec |
| `adp generate-data` | Generate synthetic data |
| `adp quality-check` | Run checks and print quality score |
| `adp semantic-model` | Build Cube.js semantic model |
| `adp sql "question"` | Convert NL to read-only SQL |
| `adp docs` | Generate data dictionary |
| `adp ui` | Start web console at http://127.0.0.1:8765 |
| `adp mcp-server` | Start MCP server for AI IDE integration |

---

## AI Provider for NL-to-SQL

```bash
export MINIMAX_API_KEY=your_key_here    # default
export OPENAI_API_KEY=your_key_here
```

Configure in `adp.yaml`:

```yaml
model_provider:
  provider: minimax
  base_url: https://api.minimax.io/v1
  model: MiniMax-Text-01
  api_key_env: MINIMAX_API_KEY
```

`provider: local` runs offline without LLM calls.

---

## Data Connectors

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

Secrets use `${ENV_VAR}` interpolation — plaintext rejected at load.

---

## Worked Examples

### Retail e-commerce (4 tables, 32/32 checks validated)

```bash
cd examples/retail-ecommerce
python make_data.py
adp init --name retail && adp connect --name shop --type csv --path ./data
adp scan && adp profile
adp generate-data --rows 50000 --output parquet
adp quality-check --report quality-report.md
```

### Customer + Transaction (declarative spec, 100/100 quality)

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

PyPI Trusted Publishing — no API tokens needed.

```bash
# Release candidate to TestPyPI
git tag v0.2.0rc1 && git push origin v0.2.0rc1

# Full release (triggered by GitHub Release)
```

See [`.github/workflows/publish.yml`](./.github/workflows/publish.yml).

---

## Contributing

Issues and PRs welcome:
- No hardcoded domain logic
- Every PR includes tests
- Secrets never in code or config

---

## License

Apache-2.0 — see [LICENSE](./LICENSE).
