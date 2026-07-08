# adp-executor (Go)

High-throughput Plan IR executor for ai-data-platform. Python compiles catalog
metadata into Plan IR JSON; this binary executes it for large-scale generation.

## Build

```bash
cd adp-executor
go mod tidy
go build -o adp-executor ./cmd/adp-executor
```

Install on PATH or place the binary at `adp-executor/adp-executor` in the repo root.

## Usage

```bash
# Export plan from Python
adp build-plan --out plan.json --rows 1000000

# Run Go executor
./adp-executor run --plan plan.json --output output/ --format parquet
```

## Python integration

In `adp.yaml`:

```yaml
generation:
  executor: auto          # python | go | auto
  go_executor_threshold_rows: 10000000
  parallel_workers: 0     # 0 = auto parallel chunk build (Python path)
```

When `executor: auto` and row count exceeds the threshold, Python dispatches to
this binary if found on PATH. Falls back to Python on failure.

## Supported samplers (v0)

- `sequence`, `uuid`, `choice`, `normal`, `uniform_int`, `words`
- FK sampling from parent key pools
- Output: `parquet`, `csv`

Derive rules (`expr`, `after`, `values_by`) are Python-only until v1.

## Contract

Plan IR schema matches `generator/engine.py` (`plan_ir_version: 1`). Same seed +
plan must produce equivalent output (row-level equivalence tests planned).
