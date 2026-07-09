"""Generation performance benchmark for the seasonal-retail spec.

Measures:
  - Wall-clock time to generate 10M rows (parquet)
  - Peak RSS memory (tracemalloc + psutil)
  - Output file sizes per table
  - Heuristic memory estimate vs actual RSS
  - Quality score
  - Seasonality score
  - Per-table generation time breakdown

Run:
    python benchmarks/bench_generation.py
"""

from __future__ import annotations

import gc
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import psutil

# Add source to path so benchmarks can run against the repo checkout
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_data_platform.config import GenerationConfig
from ai_data_platform.generator.engine import GenerationPlan, build_plan, generate
from ai_data_platform.metadata.catalog import Catalog
from ai_data_platform.optimizer import plan_execution
from ai_data_platform.sdk import ADPClient
from ai_data_platform.spec import apply_spec, load_spec


@dataclass
class BenchmarkResult:
    rows: int
    format: str
    wall_time_s: float = 0.0
    peak_rss_mb: float = 0.0
    output_size_mb: float = 0.0
    quality_score: float | None = None
    seasonality_score: float | None = None
    heuristic_memory_mb: float = 0.0
    memory_error_pct: float | None = None
    per_table_time_s: dict[str, float] = field(default_factory=dict)
    per_table_rows: dict[str, int] = field(default_factory=dict)
    per_table_size_mb: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    plan_warnings: list[str] = field(default_factory=list)


def _get_rss_mb() -> float:
    """Current process RSS in MB using psutil."""
    return psutil.Process().memory_info().rss / 1_048_576


def _get_peak_rss_mb() -> float:
    """Peak RSS so far in MB (uses children for spawned threads)."""
    me = psutil.Process()
    try:
        return me.memory_info().max_rss / 1_048_576
    except AttributeError:
        # Some platforms don't have max_rss; fall back to current RSS
        return _get_rss_mb()


class MemoryTracker:
    """Tracks peak RSS across a code block."""

    def __init__(self) -> None:
        self.start_rss: float = 0.0
        self.peak_rss: float = 0.0

    def start(self) -> None:
        gc.collect()
        self.start_rss = _get_rss_mb()
        self.peak_rss = self.start_rss

    def checkpoint(self) -> float:
        current = _get_rss_mb()
        if current > self.peak_rss:
            self.peak_rss = current
        return current

    def peak(self) -> float:
        self.checkpoint()
        return self.peak_rss - self.start_rss


def run_benchmark(
    spec_path: str,
    rows: int,
    output_format: str = "parquet",
    seed: int = 42,
    workers: int = 1,
    rows_per_table: dict[str, int] | None = None,
) -> BenchmarkResult:
    """Run generation benchmark and return results."""
    workdir = Path(tempfile.mkdtemp(prefix="adp-bench-"))
    result = BenchmarkResult(rows=rows, format=output_format)
    tracker = MemoryTracker()

    try:
        print(f"\n{'='*60}")
        print(f"BENCHMARK: {rows:,} rows | format={output_format} | workers={workers}")
        print(f"Workdir:   {workdir}")
        print(f"{'='*60}")

        # -- 1. Set up ADP project -----------------------------------------
        print("\n[1/6] Setting up ADP project...")
        t0 = time.perf_counter()
        client = ADPClient(workdir)
        client.init("bench-seasonal-retail")
        # Copy spec into workdir so safe_resolve (which guards against traversal) allows it
        spec_basename = Path(spec_path).name
        local_spec = workdir / spec_basename
        shutil.copy2(spec_path, local_spec)
        apply_result = client.apply_spec(spec_basename)
        setup_time = time.perf_counter() - t0
        print(f"  ✓ Spec applied: {apply_result['tables']} tables, "
              f"{apply_result['columns']} cols, {apply_result['relationships']} rels "
              f"in {setup_time:.1f}s")

        # -- 2. Static plan analysis ----------------------------------------
        print("\n[2/6] Static plan analysis...")
        t0 = time.perf_counter()
        plan = GenerationPlan.model_validate(client.build_plan(
            rows=rows, seed=seed, rows_per_table=rows_per_table,
        ))
        plan_time = time.perf_counter() - t0

        # Memory estimate
        cfg = client.config.generation
        ep = plan_execution(plan, cfg, memory_budget_mb=12_000)

        # -- 3b. Rebuild plan with rows_per_table for accurate analysis + generation ---
        if rows_per_table:
            plan = GenerationPlan.model_validate(
                client.build_plan(rows=rows, seed=seed, rows_per_table=rows_per_table),
            )
            ep = plan_execution(plan, cfg, memory_budget_mb=12_000)

        result.heuristic_memory_mb = ep["memory_estimate_mb"]
        result.plan_warnings = ep.get("optimization_warnings", [])

        print(f"  Plan IR:       {sum(t.rows for t in plan.tables):,} total rows "
              f"({len(plan.tables)} tables)")
        for tp in plan.tables:
            print(f"    {tp.name:<22} {tp.rows:>10,} rows  "
                  f"{len(tp.columns):>3} cols  {len(tp.foreign_keys)} FKs")
        print(f"  Heuristic mem: {result.heuristic_memory_mb:>8,.0f} MB")
        print(f"  Batch size:    {ep['recommended_batch_size']:,}  "
              f"parallelism={ep['parallelism']}  format={ep['recommended_format']}")
        print(f"  Runtime class: {ep['expected_runtime_class']}")
        if ep.get("optimization_warnings"):
            for w in ep["optimization_warnings"]:
                print(f"  ⚠ {w}")
        print(f"  Plan time:     {plan_time:.2f}s")

        # -- 3. Generate ----------------------------------------------------
        print("\n[3/6] Generating synthetic data...")
        cfg.parallel_workers = workers
        tracker.start()
        t0 = time.perf_counter()
        gen_result = generate(
            plan,
            workdir / "output",
            output_format=output_format,
            parallel_workers=workers,
        )
        gen_wall = time.perf_counter() - t0
        result.wall_time_s = gen_wall
        result.peak_rss_mb = tracker.peak()

        for name, info in gen_result.items():
            result.per_table_rows[name] = info["rows"]
            p = Path(info["path"])
            if p.exists():
                size_mb = p.stat().st_size / 1_048_576
                result.per_table_size_mb[name] = size_mb
                result.output_size_mb += size_mb
                print(f"  ✓ {name:<22} {info['rows']:>10,} rows  "
                      f"{size_mb:>8.1f} MB  → {p}")
            else:
                # DuckDB / SQL output — directory
                size_mb = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1_048_576
                result.per_table_size_mb[name] = size_mb
                result.output_size_mb += size_mb
                print(f"  ✓ {name:<22} {info['rows']:>10,} rows  "
                      f"{size_mb:>8.1f} MB  → {p}/")

        total_rows = sum(result.per_table_rows.values())
        rows_per_sec = total_rows / gen_wall if gen_wall > 0 else 0
        mb_per_sec = result.output_size_mb / gen_wall if gen_wall > 0 else 0
        print(f"\n  Generation wall time:  {gen_wall:>8.1f}s")
        print(f"  Peak RSS delta:         {result.peak_rss_mb:>8.1f} MB")
        print(f"  Total output size:      {result.output_size_mb:>8.1f} MB")
        print(f"  Throughput:             {rows_per_sec:>10,.0f} rows/s")
        print(f"  Write bandwidth:        {mb_per_sec:>10.1f} MB/s")
        print(f"  Heuristic vs actual:   {result.heuristic_memory_mb:>8,.0f} MB est "
              f"vs {result.peak_rss_mb:.0f} MB actual "
              f"(error: {((result.peak_rss_mb - result.heuristic_memory_mb) / result.heuristic_memory_mb * 100):+.0f}%)")

        # -- 4. Quality check -----------------------------------------------
        print("\n[4/6] Running quality check...")
        gc.collect()
        tracker.start()
        t0 = time.perf_counter()
        try:
            qc_result = client.quality_check(data_dir=str(workdir / "output"))
            qc_time = time.perf_counter() - t0
            result.quality_score = qc_result["quality_score"]
            print(f"  Quality score:  {result.quality_score:.0f}/100  ({qc_time:.1f}s)")
            for cat, score in qc_result.get("category_scores", {}).items():
                print(f"    {cat:<30} {score:.0f}")
            for t in qc_result.get("tables", []):
                failed = [c for c in t["checks"] if not c["passed"]]
                if failed:
                    for c in failed[:3]:
                        print(f"    ✗ {t['table']}.{c.get('column','')}: {c['evidence']}")
        except Exception as e:
            result.errors.append(f"quality_check: {e}")
            print(f"  ✗ Quality check failed: {e}")

        # -- 5. Seasonality check -------------------------------------------
        print("\n[5/6] Running seasonality check...")
        gc.collect()
        tracker.start()
        t0 = time.perf_counter()
        try:
            seas_result = client.seasonality_check(
                data_dir=str(workdir / "output"), tables=["fact_orders"]
            )
            seas_time = time.perf_counter() - t0
            result.seasonality_score = seas_result["seasonality_score"]
            print(f"  Seasonality score: {result.seasonality_score:.0f}/100  ({seas_time:.1f}s)")
            for cat, score in seas_result.get("category_scores", {}).items():
                print(f"    {cat:<30} {score:.0f}")
            for t in seas_result.get("tables", []):
                failed = [c for c in t["checks"] if not c["passed"]]
                if failed:
                    for c in failed[:3]:
                        print(f"    ✗ {t['table']}.{c.get('metric','')}: {c['evidence']}")
        except Exception as e:
            result.errors.append(f"seasonality_check: {e}")
            print(f"  ✗ Seasonality check failed: {e}")

        # -- 6. Summary ------------------------------------------------------
        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*60}")
        print(f"  Rows:              {rows:>12,}")
        print(f"  Format:            {output_format}")
        print(f"  Workers:           {workers}")
        print(f"  Wall time:         {result.wall_time_s:>12.1f}s")
        print(f"  Peak RSS delta:    {result.peak_rss_mb:>12.1f} MB")
        print(f"  Heuristic memory:  {result.heuristic_memory_mb:>12,.0f} MB")
        print(f"  Memory error:      {((result.peak_rss_mb - result.heuristic_memory_mb) / result.heuristic_memory_mb * 100):+12.1f}%")
        print(f"  Output size:       {result.output_size_mb:>12.1f} MB")
        print(f"  Throughput:        {rows_per_sec:>12,.0f} rows/s")
        print(f"  Quality score:     {result.quality_score}")
        print(f"  Seasonality score: {result.seasonality_score}")
        if result.errors:
            print(f"  Errors:            {result.errors}")

    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    return result


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Generation performance benchmark")
    ap.add_argument("--rows", type=int, default=10_000_000, help="Default rows per table (default: 10M)")
    ap.add_argument("--rows-per-table", "-rpt", default=None,
                     help='Per-table counts: "fact_orders=10M,fact_payments=10M,fact_shipments=10M"')
    ap.add_argument("--format", "-f", default="parquet", help="Output format (default: parquet)")
    ap.add_argument("--spec", "-s", default="benchmarks/fixtures/seasonal-retail-spec.yaml",
                     help="Path to spec.yaml")
    ap.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    ap.add_argument("--workers", "-w", type=int, default=1, help="Parallel workers (default: 1)")
    ap.add_argument("--json", "-j", action="store_true", help="Emit JSON results")
    args = ap.parse_args()

    # Parse rows-per-table
    rows_per_table: dict[str, int] | None = None
    if args.rows_per_table:
        try:
            rows_per_table = {
                kv.split("=")[0].strip(): int(kv.split("=")[1])
                for kv in args.rows_per_table.split(",")
            }
        except (IndexError, ValueError):
            print("--rows-per-table format: table=count,table2=count")
            sys.exit(1)

    # Resolve spec relative to repo root
    repo_root = Path(__file__).parent.parent
    spec_path = repo_root / args.spec

    result = run_benchmark(
        spec_path=str(spec_path),
        rows=args.rows,
        output_format=args.format,
        seed=args.seed,
        workers=args.workers,
        rows_per_table=rows_per_table,
    )

    if args.json:
        import json
        print(json.dumps({
            "rows": result.rows,
            "format": result.format,
            "wall_time_s": round(result.wall_time_s, 2),
            "peak_rss_mb": round(result.peak_rss_mb, 1),
            "output_size_mb": round(result.output_size_mb, 1),
            "quality_score": result.quality_score,
            "seasonality_score": result.seasonality_score,
            "heuristic_memory_mb": round(result.heuristic_memory_mb, 1),
            "memory_error_pct": round(((result.peak_rss_mb - result.heuristic_memory_mb) / result.heuristic_memory_mb * 100), 1) if result.heuristic_memory_mb else None,
            "per_table_rows": result.per_table_rows,
            "per_table_size_mb": {k: round(v, 1) for k, v in result.per_table_size_mb.items()},
            "plan_warnings": result.plan_warnings,
            "errors": result.errors,
        }, indent=2))


if __name__ == "__main__":
    main()
