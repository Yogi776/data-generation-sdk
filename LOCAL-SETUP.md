# Local Setup — step by step (macOS)

## 1. Install (one time)

```bash
cd ~/experiment-personal/"Data Generator"/ai-data-platform

python3 -m venv .venv               # needs Python 3.11+ (check: python3 --version)
source .venv/bin/activate
pip install -e ".[dev,all]"

adp version                          # → ai-data-platform 0.1.0
```

Every new terminal session: `source .venv/bin/activate` first (or add the venv's
bin to PATH).

## 2. Fastest path — generate from config only (no data needed)

```bash
mkdir ~/my-dataset && cd ~/my-dataset
adp init

# copy a ready spec to start from:
cp ~/experiment-personal/"Data Generator"/ai-data-platform/examples/healthcare/spec.yaml .
#   (or examples/customer-transaction/spec.yaml for the 98-column e-commerce model)

adp apply-spec spec.yaml
adp generate-data --rows 50000 --output parquet
adp quality-check --report quality.md
```

Output lands in `~/my-dataset/output/`. Edit spec.yaml (tables, values weights,
joins, expr/after/null_unless/values_by dependencies) and regenerate.

## 3. Alternative path — learn from your real sample data

```bash
cd ~/my-dataset
# put CSVs (or parquet/duckdb) into ./data — a few hundred representative rows per table
adp connect --name src --type csv --path ./data
adp scan && adp profile
adp generate-data --rows 100000
adp quality-check
```

Postgres/MySQL instead of files:

```bash
export PGPASSWORD=yourpassword    # or put in .env
adp connect --name db --type postgres \
  --dsn "postgresql+psycopg://user:\${PGPASSWORD}@localhost:5432/mydb" --schema public
```

## 4. Extras

```bash
adp semantic-model --format cube --out model/cubes.yml    # Cube.js models
adp docs                                                  # data dictionary
adp ui                                                    # web console → http://127.0.0.1:8765
adp sql "revenue by city last month"                      # needs MINIMAX_API_KEY in .env
```

## 5. MCP — drive it from Claude / Cursor

```bash
# Claude Code:
claude mcp add adp -- ~/experiment-personal/"Data Generator"/ai-data-platform/.venv/bin/adp \
  mcp-server --project ~/my-dataset
```

Claude Desktop / Cursor / Windsurf — add to their mcp config json:

```json
{
  "mcpServers": {
    "adp": {
      "command": "/Users/yogeshkhangode/experiment-personal/Data Generator/ai-data-platform/.venv/bin/adp",
      "args": ["mcp-server", "--project", "/Users/yogeshkhangode/my-dataset"]
    }
  }
}
```

Then just ask the agent: "generate 10k rows of test data and run a quality check."

### Testing in Cursor, step by step

1. Create a project folder and initialize it once:

   ```bash
   mkdir ~/adp-cursor-test && cd ~/adp-cursor-test
   source ~/experiment-personal/"Data Generator"/ai-data-platform/.venv/bin/activate
   adp init
   ```

2. Add the server to Cursor — create/edit `~/.cursor/mcp.json`
   (or Cursor Settings → MCP → Add new global MCP server):

   ```json
   {
     "mcpServers": {
       "adp": {
         "command": "/Users/yogeshkhangode/experiment-personal/Data Generator/ai-data-platform/.venv/bin/adp",
         "args": ["mcp-server", "--project", "/Users/yogeshkhangode/adp-cursor-test"]
       }
     }
   }
   ```

3. Restart Cursor → Settings → MCP: "adp" should show a green dot and
   11 tools (apply_spec, generate_synthetic_data, preview_data, …).

4. In Cursor chat (Agent mode), test config-only generation with a prompt like:

   > Using the adp tools: apply a dataset spec for a small e-commerce model —
   > customers (customer_id uuid pk, name, city with weights Pune 60/Mumbai 40)
   > and orders (order_id uuid pk, customer_id one-to-many from customers,
   > amount float mean 900, status delivered 90/returned 10). Then generate
   > 5,000 rows, run a quality check, and preview 5 rows of orders.

   Cursor will call `apply_spec` → `generate_synthetic_data` →
   `run_quality_check` → `preview_data` and report the quality score.

5. Files land in `~/adp-cursor-test/output/` — open them right in Cursor.

If tools don't appear: check the `command` path exists (`ls` it), use absolute
paths only, and view Cursor's MCP logs (Output panel → "MCP") for stderr.

## 6. Verify the install (optional)

```bash
cd ~/experiment-personal/"Data Generator"/ai-data-platform
pytest          # 70 tests
ruff check .
```

## Troubleshooting

- `ResolutionTooDeep` / endless pip resolve → your venv is Python 3.10 or older
  (check the path in the traceback: `.venv/lib/python3.10/`). The package needs
  3.11+. Fix: `rm -rf .venv && python3.12 -m venv .venv && source .venv/bin/activate
  && pip install --upgrade pip && pip install -e ".[dev,all]"`
  (install 3.12 first if needed: `brew install python@3.12`).
- `command not found: adp` → activate the venv (`source .venv/bin/activate`).
- `disk I/O error` on network drives → `export ADP_CATALOG_DIR=~/.adp-catalogs`.
- Python < 3.11 → `brew install python@3.12`, then create the venv with `python3.12 -m venv .venv`.
- Full docs: README.md · docs/USER-FLOW.md · docs/ARCHITECTURE.md · examples/*/INSTRUCTIONS.md
