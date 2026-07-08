"""Generation engine.

1. `build_plan` compiles catalog metadata into a GenerationPlan — a
   language-neutral, Plan-IR-shaped document (json-serializable) so future
   executors (platform Go workers, ADR-0010) can run the same plan.
2. `generate` executes the plan: parents before children, FK-safe,
   deterministic per (seed, table), chunked to bound memory.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl
from pydantic import BaseModel, Field

from ai_data_platform.core.exceptions import GenerationError
from ai_data_platform.core.logging import get_logger
from ai_data_platform.generator.samplers import SamplerSpec, build_sampler, infer_sampler
from ai_data_platform.generator.writers import write_output

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from ai_data_platform.metadata.catalog import Catalog

log = get_logger("adp.generate")

PLAN_IR_VERSION = 1


class ColumnPlan(BaseModel):
    name: str
    sampler: str
    params: dict[str, Any] = Field(default_factory=dict)
    null_ratio: float = 0.0
    # cross-column dependencies: {"expr": sql, "after": {...}, "null_unless": sql}
    derive: dict[str, Any] | None = None


class ForeignKeyPlan(BaseModel):
    column: str
    parent_table: str
    parent_column: str
    relationship: str = "many_to_one"  # many_to_one | one_to_one


class TablePlan(BaseModel):
    name: str
    rows: int
    columns: list[ColumnPlan]
    foreign_keys: list[ForeignKeyPlan] = Field(default_factory=list)


class GenerationPlan(BaseModel):
    """Plan IR v1: partitionable, executor-neutral generation spec."""

    plan_ir_version: int = PLAN_IR_VERSION
    seed: int
    chunk_rows: int = 100_000
    tables: list[TablePlan]


def _topo_sort(tables: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Parents-first order; cycles broken by dropping back-edges (logged)."""
    deps: dict[str, set[str]] = {t: set() for t in tables}
    for child, parent in edges:
        if child in deps and parent in deps and child != parent:
            deps[child].add(parent)
    ordered: list[str] = []
    remaining = dict(deps)
    while remaining:
        ready = sorted(t for t, d in remaining.items() if not d)
        if not ready:  # cycle: break it deterministically
            victim = sorted(remaining)[0]
            log.warning("relationship cycle detected; breaking at %s", victim)
            remaining[victim] = set()
            continue
        for t in ready:
            ordered.append(t)
            del remaining[t]
            for d in remaining.values():
                d.discard(t)
    return ordered


def build_plan(
    catalog: Catalog,
    *,
    rows: int,
    seed: int,
    tables: list[str] | None = None,
    rows_per_table: dict[str, int] | None = None,
    chunk_rows: int = 100_000,
    fk_confidence_min: float = 0.5,
) -> GenerationPlan:
    """Compile catalog metadata (+latest profiles) into a GenerationPlan."""
    all_tables = [t["table"] for t in catalog.list_tables()]
    selected = tables or all_tables
    unknown = set(selected) - set(all_tables)
    if unknown:
        raise GenerationError(
            f"Tables not in catalog: {', '.join(sorted(unknown))}",
            hint="Run `adp scan` first, or check table names with `adp ui` / catalog search.",
        )
    if not selected:
        raise GenerationError(
            "The catalog has no tables to generate from.",
            hint="Run `adp connect` and `adp scan` first.",
        )

    rels = [
        r
        for r in catalog.get_relationships()
        if r["confidence"] >= fk_confidence_min
        and r["child_table"] in selected
        and r["parent_table"] in selected
    ]
    order = _topo_sort(selected, [(r["child_table"], r["parent_table"]) for r in rels])

    plans: list[TablePlan] = []
    for tbl in order:
        meta = catalog.get_table(tbl)
        profile = catalog.get_latest_profile(tbl) or {}
        col_profiles = {c["name"]: c for c in profile.get("columns", [])}
        fk_cols = {
            r["child_column"]: ForeignKeyPlan(
                column=r["child_column"],
                parent_table=r["parent_table"],
                parent_column=r["parent_column"],
                relationship=r.get("kind", "many_to_one"),
            )
            for r in rels
            if r["child_table"] == tbl
        }
        columns: list[ColumnPlan] = []
        for col in meta["columns"]:
            if col["name"] in fk_cols:
                continue  # filled from parent keys at execution time
            spec: SamplerSpec = infer_sampler(
                col, col_profiles.get(col["name"]), is_pk=col["primary_key"]
            )
            null_ratio = float(col_profiles.get(col["name"], {}).get("null_ratio", 0.0) or 0.0)
            columns.append(
                ColumnPlan(
                    name=col["name"],
                    sampler=spec.sampler,
                    params=spec.params,
                    # honor profiled sparsity (e.g. coupon_code 65% null); keys never null
                    null_ratio=0.0 if col["primary_key"] else min(null_ratio, 0.95),
                    derive=col_profiles.get(col["name"], {}).get("derive"),
                )
            )
        # precedence: explicit per-table override > spec-declared rows > global rows
        table_rows = (rows_per_table or {}).get(tbl) or profile.get("spec_rows") or rows
        plans.append(
            TablePlan(
                name=tbl,
                rows=int(table_rows),
                columns=columns,
                foreign_keys=list(fk_cols.values()),
            )
        )
    return GenerationPlan(seed=seed, chunk_rows=chunk_rows, tables=plans)


def _table_rng(seed: int, table: str, chunk: int) -> np.random.Generator:
    """Deterministic per (seed, table, chunk) — partition-parallel safe."""
    digest = hashlib.sha256(f"{seed}:{table}:{chunk}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


# guard for derive expressions: identifiers, numbers, arithmetic, comparisons,
# quoted literals, CASE WHEN — no statement separators or function-call abuse
_SAFE_EXPR = re.compile(r"^[\w\s\.\+\-\*/\(\)'\"=<>!%,]+$")


def _guarded_sql_expr(expression: str) -> pl.Expr:
    if not _SAFE_EXPR.match(expression) or ";" in expression:
        raise GenerationError(
            f"Unsafe derive expression: {expression!r}",
            hint="Allowed: column names, numbers, + - * / ( ), comparisons, "
            "quoted literals, CASE WHEN.",
        )
    try:
        return pl.sql_expr(expression)
    except Exception as e:
        raise GenerationError(f"Invalid derive expression {expression!r}: {e}") from e


def _apply_derives(df: pl.DataFrame, tp: TablePlan, rng: np.random.Generator) -> pl.DataFrame:
    """Apply cross-column dependencies in declared column order.

    Supported per column:
      after:       {column, min_minutes, max_minutes} — value = other + random offset
      expr:        SQL arithmetic over sibling columns (subtotal = price*qty - discount)
      null_unless: SQL condition — value nulled where the condition is false
    """
    for cp in tp.columns:
        d = cp.derive or {}
        if not d:
            continue
        if d.get("conditional"):
            c = d["conditional"]
            base, mapping = c["column"], c["mapping"]
            if base not in df.columns:
                raise GenerationError(
                    f"values_by on {tp.name}.{cp.name}: column {base!r} not found."
                )
            parent = df.get_column(base).cast(pl.String).to_numpy()
            out: list[Any] = [None] * len(df)
            for pv, dist in mapping.items():
                mask = np.nonzero(parent == pv)[0]
                if len(mask) == 0:
                    continue
                vals = list(dist.keys())
                w = np.asarray(list(dist.values()), dtype=float)
                picks = rng.choice(len(vals), size=len(mask), p=w / w.sum())
                for i, p_idx in zip(mask, picks):
                    out[int(i)] = vals[int(p_idx)]
            df = df.with_columns(pl.Series(cp.name, out))
        if d.get("after"):
            a = d["after"]
            base = a["column"]
            if base not in df.columns:
                raise GenerationError(
                    f"derive.after on {tp.name}.{cp.name}: column {base!r} not found."
                )
            lo = int(a.get("min_minutes", 1))
            hi = max(int(a.get("max_minutes", 1440)), lo + 1)
            offs = pl.Series("_adp_off", rng.integers(lo, hi, size=len(df)))
            df = (
                df.with_columns(offs)
                .with_columns(
                    (pl.col(base) + pl.duration(minutes=pl.col("_adp_off"))).alias(cp.name)
                )
                .drop("_adp_off")
            )
        if d.get("expr"):
            df = df.with_columns(_guarded_sql_expr(str(d["expr"])).alias(cp.name))
        if d.get("null_unless"):
            cond = _guarded_sql_expr(str(d["null_unless"]))
            df = df.with_columns(pl.when(cond).then(pl.col(cp.name)).otherwise(None).alias(cp.name))
    return df


def generate(
    plan: GenerationPlan,
    output_dir: str | Path,
    *,
    output_format: str = "parquet",
) -> dict[str, Any]:
    """Execute a plan. Returns {table: {rows, path}}."""
    key_pool: dict[tuple[str, str], pl.Series] = {}
    results: dict[str, Any] = {}

    for tp in plan.tables:
        # one_to_one FKs: a unique permutation of parent keys (no reuse)
        o2o_perm: dict[str, np.ndarray] = {}
        for fk in tp.foreign_keys:
            if fk.relationship != "one_to_one":
                continue
            pool = key_pool.get((fk.parent_table, fk.parent_column))
            if pool is not None and tp.rows > len(pool):
                raise GenerationError(
                    f"one_to_one join {tp.name}.{fk.column} -> {fk.parent_table}."
                    f"{fk.parent_column}: {tp.rows} rows requested but parent has "
                    f"only {len(pool)} keys.",
                    hint="For 1:1 joins the child cannot have more rows than the parent.",
                )
            if pool is not None:
                o2o_perm[fk.column] = _table_rng(
                    plan.seed, f"{tp.name}:o2o:{fk.column}", 0
                ).permutation(len(pool))

        frames: list[pl.DataFrame] = []
        remaining = tp.rows
        chunk_idx = 0
        while remaining > 0:
            n = min(remaining, plan.chunk_rows)
            offset = tp.rows - remaining
            rng = _table_rng(plan.seed, tp.name, chunk_idx)
            data: dict[str, pl.Series] = {}
            for cp in tp.columns:
                sampler = build_sampler(SamplerSpec(cp.sampler, dict(cp.params)))
                if cp.sampler == "sequence":
                    start = offset + int(cp.params.get("start", 1))
                    sampler = build_sampler(SamplerSpec("sequence", {"start": start}))
                series = sampler(rng, n)
                if cp.null_ratio > 0:
                    mask = pl.Series(rng.random(n) < cp.null_ratio)
                    series = (
                        pl.DataFrame({"v": series, "m": mask})
                        .select(pl.when(pl.col("m")).then(None).otherwise(pl.col("v")).alias("v"))
                        .get_column("v")
                    )
                data[cp.name] = series
            for fk in tp.foreign_keys:
                pool = key_pool.get((fk.parent_table, fk.parent_column))
                if pool is None or len(pool) == 0:
                    raise GenerationError(
                        f"No parent keys for {tp.name}.{fk.column} -> "
                        f"{fk.parent_table}.{fk.parent_column}.",
                        hint="Parent table must be generated in the same run "
                        "(check relationships with `adp scan`).",
                    )
                if fk.column in o2o_perm:
                    idx = o2o_perm[fk.column][offset : offset + n]
                else:
                    idx = rng.integers(0, len(pool), size=n)
                data[fk.column] = pl.Series(pool.gather(idx))
            chunk_df = _apply_derives(pl.DataFrame(data), tp, rng)
            frames.append(chunk_df)
            remaining -= n
            chunk_idx += 1

        df = pl.concat(frames) if len(frames) > 1 else frames[0]
        # register this table's PK values for children
        for cp in tp.columns:
            if cp.sampler in ("sequence", "uuid"):
                key_pool[(tp.name, cp.name)] = df.get_column(cp.name)
        path = write_output(df, tp.name, output_dir, output_format)
        results[tp.name] = {"rows": len(df), "path": str(path)}
        log.info("generated %s: %d rows -> %s", tp.name, len(df), path)
    return results
