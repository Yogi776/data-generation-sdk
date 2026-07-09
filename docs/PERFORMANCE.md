# Performance & Scaling

The platform is already built for scale: generation is **vectorized** (polars/numpy),
**chunked-streaming**, **parallel-by-chunk**, uses **deterministic per-`(seed,table,chunk)`** RNG
and **vectorized FK joins**; validation and seasonality checks run as **DuckDB aggregate SQL**; the
query layer uses **DuckDB views with predicate/projection pushdown**. This page covers the
**planning layer** that sizes a run *before* you launch it, and the roadmap for the remaining
generation-side scale work.

## Execution planner

`adp plan-execution` compiles your spec into the Plan-IR and returns an execution plan — the same
row-count resolution `adp generate-data` uses (per-table `rows:` overrides `--rows`), so the plan
reflects what would actually run.

```bash
adp plan-execution spec.yaml --rows 100000000            # apply spec, then plan
adp plan-execution --rows 100000000 --memory-budget-mb 8000 --json
adp analyze-complexity --rows 100000000                  # module + per-table cost table
adp generate-data --rows 100000000 --optimized           # apply the plan's batch/parallelism/format
```

Plan JSON:

```json
{
  "estimated_rows": 100000000,
  "recommended_batch_size": 100000,
  "recommended_format": "parquet",
  "partition_by": ["order_ts"],
  "parallelism": 8,
  "memory_estimate_mb": 22018,
  "expected_runtime_class": "xlarge",
  "optimization_warnings": ["estimated peak 22018 MB exceeds budget 4096 MB — ..."]
}
```

(plus additive `per_table`, `memory`, `partitioning`, and `complexity` blocks.)

### What it computes
- **memory_estimate_mb** — models the engine's *actual* behavior: `generate()` materializes every
  chunk of a table into a list before writing, so per-table peak is whole-table (`row_bytes × rows
  × ~2` overhead), **plus** the `key_pool` (parent keys + inherited columns retained for the whole
  run) **plus** one_to_one permutation arrays. Column widths are heuristic by sampler/dtype.
- **recommended_batch_size / parallelism** — chosen so one worker's chunk working set fits a fair
  share of the memory budget (default 4096 MB); parallelism ≤ `min(cpu-2, chunk_count, 16)`.
- **recommended_format** — parquet for ≥1M-row tables, else your configured default.
- **partition_by** — the largest table's seasonal anchor / date column (month buckets), else a
  low-cardinality categorical, else none.
- **expected_runtime_class** — small <1M · medium <10M · large <100M · xlarge ≥100M total rows.
- **optimization_warnings** — memory-over-budget, whole-table materialization, GIL-bound per-row
  string samplers, large FK key_pool fan-in, small-file / partition-explosion, and single-file-at-
  scale (recommend partitioned output).

## Complexity table

| Module | Time | Space | Note |
|---|---|---|---|
| generation (numeric) | O(rows) | O(chunk) | numpy-vectorized, GIL-releasing |
| generation (string) | O(rows) | O(chunk) | per-row Python; GIL-bound (Phase 3) |
| FK resolution | O(rows) | O(parent keys) | vectorized gather; key_pool retained |
| seasonality | O(days)+O(rows) | O(days) | curve O(days); sampling O(rows) |
| write (parquet/csv) | O(rows) | O(chunk) | streaming row-group per chunk |
| validation (DuckDB) | O(rows) scan | O(1) | aggregate SQL, streaming |
| profiling (source) | O(sample) | O(file) | full-file load then sample (Phase 3) |
| query/export | O(scan) | O(result) | pushdown + LIMIT/scan-guard |

## Scaling guidance

- **1M rows** — laptop-friendly as-is; parquet recommended.
- **100M rows** — use `--optimized`; watch the memory warning. Until Phase 2/3 land, keep the
  *largest table* within the whole-table memory bound (or split runs) — the planner tells you the
  number. Partitioned output (Phase 2) removes the single-file problem.
- **1B+/1TB** — needs partition-parallel generation over the partition plan and DuckDB lazy scan
  across partitioned Parquet (Phase 4).

## Optimization roadmap (next phases)

The planner surfaces exactly what these phases fix:

- **Phase 2 — Partitioned Parquet output.** Generation-side Hive writer keyed on the planner's
  `partition_by`, consumed by the already partition-aware explorer for pruning. Makes `partition_by`
  actionable, not just advisory.
- **Phase 2 — Benchmark harness** (`adp benchmark`): rows/sec, MB/sec, peak memory, output size;
  row-by-row vs vectorized, CSV vs Parquet, serial vs parallel; before/after report. Builds on
  `scripts/benchmark_performance.py`.
- **Phase 3 — Streaming + vectorization.** Stream chunk→write (remove the whole-table `ordered`
  list); vectorize the per-row Python string samplers (`uuid`/`template`/`words`/`full_name`/
  `email`/`address`/`choice`) and datetime construction; parallelize independent tables (topo
  levels); cache the seasonal day-weight curve across chunks.
- **Phase 3 — Source profiler → DuckDB.** Replace the full-file Polars load in `profiler/profiler.py`
  with `SUMMARIZE`/aggregate SQL; FK inclusion via DuckDB anti-join; streaming `COPY TO` export.
- **Phase 4 — 1B/1TB.** Partition-parallel/distributed generation; DuckDB lazy scan over partitions.
