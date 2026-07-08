#!/usr/bin/env python3
"""Compare performance: sequential vs parallel generation, DuckDB vs Polars quality."""

from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_data_platform.generator.engine import GenerationPlan, generate  # noqa: E402
from ai_data_platform.quality.checks import run_quality_checks  # noqa: E402
from ai_data_platform.quality.duckdb_checks import run_quality_checks_on_dir  # noqa: E402
from ai_data_platform.sdk import ADPClient  # noqa: E402


def _timed(fn, runs: int = 3) -> dict[str, float]:
    times: list[float] = []
    result = None
    for _ in range(runs):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return {
        "min_s": min(times),
        "mean_s": statistics.mean(times),
        "max_s": max(times),
        "result": result,
    }


def _setup_retail_client() -> ADPClient:
    retail = ROOT.parent / "retail"
    if not (retail / "adp.yaml").exists():
        raise SystemExit("retail project not found")
    client = ADPClient(retail)
    if not client.catalog.list_tables():
        client.apply_spec("spec.yaml")
    return client


def bench_generation(client: ADPClient, rows: int, runs: int = 3) -> dict:
    plan_dict = client.build_plan(rows=rows, seed=42)
    plan = GenerationPlan.model_validate(plan_dict)
    base = client.root / ".bench" / f"gen_{rows}"

    def seq():
        out = base / "sequential"
        shutil.rmtree(out, ignore_errors=True)
        return generate(plan, out, output_format="parquet", parallel_workers=1)

    def par():
        out = base / "parallel"
        shutil.rmtree(out, ignore_errors=True)
        workers = min(__import__("os").cpu_count() or 1, 8)
        return generate(plan, out, output_format="parquet", parallel_workers=workers)

    s = _timed(seq, runs)
    p = _timed(par, runs)
    total_rows = sum(t["rows"] for t in plan_dict["tables"])
    return {
        "rows_per_table": rows,
        "total_rows": total_rows,
        "tables": len(plan_dict["tables"]),
        "sequential_mean_s": round(s["mean_s"], 4),
        "parallel_mean_s": round(p["mean_s"], 4),
        "speedup": round(s["mean_s"] / p["mean_s"], 2) if p["mean_s"] > 0 else 0,
        "workers": min(__import__("os").cpu_count() or 1, 8),
    }


def bench_quality(client: ADPClient, rows: int, runs: int = 3) -> dict:
    out = client.root / ".bench" / f"qc_{rows}"
    shutil.rmtree(out, ignore_errors=True)
    client.generate_data(rows=rows, seed=42, output_format="parquet", output_dir=str(out.relative_to(client.root)))

    def duckdb():
        return run_quality_checks_on_dir(client.catalog, out)

    def polars():
        known = {t["table"] for t in client.catalog.list_tables()}
        data: dict[str, pl.DataFrame] = {}
        for f in sorted(out.glob("*.parquet")):
            if f.stem in known:
                data[f.stem] = pl.read_parquet(f)
        return run_quality_checks(client.catalog, data)

    d = _timed(duckdb, runs)
    p = _timed(polars, runs)
    return {
        "rows_per_table": rows,
        "duckdb_mean_s": round(d["mean_s"], 4),
        "polars_mean_s": round(p["mean_s"], 4),
        "speedup": round(p["mean_s"] / d["mean_s"], 2) if d["mean_s"] > 0 else 0,
        "scores_match": d["result"]["quality_score"] == p["result"]["quality_score"],
    }


def bench_sql_writer(rows: int = 50_000, runs: int = 3) -> dict:
    """Compare old iter_rows SQL writer vs new column-vectorized writer."""
    import numpy as np
    from ai_data_platform.generator import writers

    rng = np.random.default_rng(42)
    df = pl.DataFrame(
        {
            "id": np.arange(1, rows + 1),
            "name": [f"user_{i}@example.com" for i in range(rows)],
            "amount": np.round(rng.lognormal(4, 0.5, rows), 2),
            "active": rng.choice([True, False], rows),
        }
    )

    def _sql_literal(v: object) -> str:
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, int | float):
            return str(v)
        s = str(v).replace("'", "''")
        return f"'{s}'"

    def old_block(data: pl.DataFrame, table: str, batch: int = 500) -> str:
        cols = ", ".join(f'"{c}"' for c in data.columns)
        lines: list[str] = []
        buf: list[str] = []
        for row in data.iter_rows():
            buf.append("(" + ", ".join(_sql_literal(v) for v in row) + ")")
            if len(buf) >= batch:
                lines.append(f'INSERT INTO "{table}" ({cols}) VALUES\n' + ",\n".join(buf) + ";")
                buf = []
        if buf:
            lines.append(f'INSERT INTO "{table}" ({cols}) VALUES\n' + ",\n".join(buf) + ";")
        return "\n".join(lines) + "\n"

    def run_old():
        return old_block(df, "t")

    def run_new():
        return writers._sql_insert_block(df, "t")

    o = _timed(run_old, runs)
    n = _timed(run_new, runs)
    return {
        "rows": rows,
        "iter_rows_mean_s": round(o["mean_s"], 4),
        "vectorized_mean_s": round(n["mean_s"], 4),
        "speedup": round(o["mean_s"] / n["mean_s"], 2) if n["mean_s"] > 0 else 0,
    }


def bench_go_executor(client: ADPClient, rows: int, runs: int = 3) -> dict | None:
    go_bin = ROOT / "adp-executor" / "adp-executor"
    if not go_bin.is_file():
        built = shutil.which("adp-executor")
        if not built:
            return None
        go_bin = Path(built)

    plan_path = client.root / ".bench" / "plan_go.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(client.build_plan(rows=rows, seed=42)), encoding="utf-8")

    py_out = client.root / ".bench" / f"go_cmp_{rows}" / "python"
    go_out = client.root / ".bench" / f"go_cmp_{rows}" / "go"
    shutil.rmtree(py_out, ignore_errors=True)
    shutil.rmtree(go_out, ignore_errors=True)

    plan = GenerationPlan.model_validate(client.build_plan(rows=rows, seed=42))

    def run_py():
        return generate(plan, py_out, output_format="csv", parallel_workers=1)

    def run_go():
        proc = subprocess.run(
            [
                str(go_bin),
                "run",
                "--plan",
                str(plan_path),
                "--output",
                str(go_out),
                "--format",
                "csv",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        return json.loads(proc.stdout)["result"]

    try:
        p = _timed(run_py, runs)
        g = _timed(run_go, runs)
    except RuntimeError as e:
        return {"error": str(e), "note": "Go v0 supports limited samplers; retail plan may fail"}

    return {
        "rows_per_table": rows,
        "python_csv_mean_s": round(p["mean_s"], 4),
        "go_csv_mean_s": round(g["mean_s"], 4),
        "speedup": round(p["mean_s"] / g["mean_s"], 2) if g["mean_s"] > 0 else 0,
        "note": "Go v0: csv only, subset of samplers; retail uses derives — use simple plan",
    }


def bench_format(client: ADPClient, rows: int, runs: int = 3) -> dict:
    def csv():
        out = client.root / ".bench" / "fmt_csv"
        shutil.rmtree(out, ignore_errors=True)
        return client.generate_data(
            rows=rows, seed=42, output_format="csv", output_dir=str(out.relative_to(client.root))
        )

    def parquet():
        out = client.root / ".bench" / "fmt_parquet"
        shutil.rmtree(out, ignore_errors=True)
        return client.generate_data(
            rows=rows, seed=42, output_format="parquet", output_dir=str(out.relative_to(client.root))
        )

    c = _timed(csv, runs)
    p = _timed(parquet, runs)
    return {
        "csv_mean_s": round(c["mean_s"], 4),
        "parquet_mean_s": round(p["mean_s"], 4),
        "speedup": round(c["mean_s"] / p["mean_s"], 2) if p["mean_s"] > 0 else 0,
    }


def bench_go_simple(rows: int = 500_000, runs: int = 3) -> dict | None:
    """Simple 2-table plan both executors can run."""
    go_bin = ROOT / "adp-executor" / "adp-executor"
    if not go_bin.is_file():
        return None

    plan = {
        "plan_ir_version": 1,
        "seed": 42,
        "chunk_rows": 100_000,
        "tables": [
            {
                "name": "customers",
                "rows": rows,
                "columns": [{"name": "customer_id", "sampler": "sequence", "params": {"start": 1}, "null_ratio": 0}],
                "foreign_keys": [],
            },
            {
                "name": "orders",
                "rows": rows * 2,
                "columns": [{"name": "order_id", "sampler": "uuid", "params": {}, "null_ratio": 0}],
                "foreign_keys": [
                    {
                        "column": "customer_id",
                        "parent_table": "customers",
                        "parent_column": "customer_id",
                        "relationship": "many_to_one",
                    }
                ],
            },
        ],
    }
    bench_dir = ROOT / ".bench_simple"
    bench_dir.mkdir(exist_ok=True)
    plan_path = bench_dir / "simple_plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    py_out = bench_dir / "python"
    go_out = bench_dir / "go"
    gen_plan = GenerationPlan.model_validate(plan)

    def run_py():
        shutil.rmtree(py_out, ignore_errors=True)
        return generate(gen_plan, py_out, output_format="csv", parallel_workers=1)

    def run_go():
        shutil.rmtree(go_out, ignore_errors=True)
        proc = subprocess.run(
            [str(go_bin), "run", "--plan", str(plan_path), "--output", str(go_out), "--format", "csv"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        return json.loads(proc.stdout)["result"]

    p = _timed(run_py, runs)
    g = _timed(run_go, runs)
    return {
        "customers": rows,
        "orders": rows * 2,
        "python_csv_mean_s": round(p["mean_s"], 4),
        "go_csv_mean_s": round(g["mean_s"], 4),
        "speedup": round(p["mean_s"] / g["mean_s"], 2) if g["mean_s"] > 0 else 0,
    }


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print(f"=== ADP Performance Benchmark (runs={runs}) ===\n")

    client = _setup_retail_client()
    cpu = __import__("os").cpu_count() or 1
    print(f"Machine: {cpu} CPU cores | Project: retail ({len(client.catalog.list_tables())} tables)\n")

    print("## 1. Generation: sequential vs parallel (parquet)")
    print("| Rows/table | Total rows | Sequential | Parallel | Speedup |")
    print("|---|---|---|---|---|")
    for rows in (1_000, 10_000, 50_000, 100_000):
        r = bench_generation(client, rows, runs)
        print(
            f"| {r['rows_per_table']:,} | {r['total_rows']:,} | "
            f"{r['sequential_mean_s']}s | {r['parallel_mean_s']}s | {r['speedup']}x |"
        )

    print("\n## 2. Quality check: Polars (full load) vs DuckDB (streaming)")
    print("| Rows/table | Polars | DuckDB | Speedup | Scores match |")
    print("|---|---|---|---|---|")
    for rows in (1_000, 10_000, 50_000, 100_000):
        r = bench_quality(client, rows, runs)
        print(
            f"| {r['rows_per_table']:,} | {r['polars_mean_s']}s | {r['duckdb_mean_s']}s | "
            f"{r['speedup']}x | {r['scores_match']} |"
        )

    print("\n## 3. SQL writer: iter_rows vs vectorized")
    print("| Rows | iter_rows | vectorized | Speedup |")
    print("|---|---|---|---|")
    for rows in (10_000, 50_000, 100_000):
        r = bench_sql_writer(rows, runs)
        print(
            f"| {r['rows']:,} | {r['iter_rows_mean_s']}s | {r['vectorized_mean_s']}s | {r['speedup']}x |"
        )

    print("\n## 4. Output format: csv vs parquet (50k rows/table)")
    fmt = bench_format(client, 50_000, runs)
    print(f"| csv | {fmt['csv_mean_s']}s |")
    print(f"| parquet | {fmt['parquet_mean_s']}s |")
    print(f"| parquet speedup | {fmt['speedup']}x |")

    print("\n## 5. Go executor vs Python (simple 2-table plan, csv)")
    simple = bench_go_simple(200_000, runs)
    if simple:
        print(
            f"customers={simple['customers']:,}, orders={simple['orders']:,} | "
            f"Python {simple['python_csv_mean_s']}s | Go {simple['go_csv_mean_s']}s | "
            f"{simple['speedup']}x"
        )
    else:
        print("(Go binary not built — skip)")

    go_retail = bench_go_executor(client, 10_000, runs=1)
    if go_retail and "error" in go_retail:
        print(f"\nRetail plan on Go: {go_retail['error'][:120]}...")
        print("(Expected — retail spec uses derives/expr not yet in Go v0)")


if __name__ == "__main__":
    main()
