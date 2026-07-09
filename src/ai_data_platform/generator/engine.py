"""Generation engine.

1. `build_plan` compiles catalog metadata into a GenerationPlan — a
   language-neutral, Plan-IR-shaped document (json-serializable) so future
   executors (platform Go workers, ADR-0010) can run the same plan.
2. `generate` executes the plan: parents before children, FK-safe,
   deterministic per (seed, table), chunked to bound memory.
"""

from __future__ import annotations

import hashlib
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl
from pydantic import BaseModel, Field

from ai_data_platform.core.exceptions import GenerationError
from ai_data_platform.core.graph import topo_sort
from ai_data_platform.core.logging import get_logger
from ai_data_platform.generator.samplers import SamplerSpec, build_sampler, infer_sampler
from ai_data_platform.generator.writers import ChunkWriter

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


class InheritPlan(BaseModel):
    """Carry a parent column across the FK into the child (seasonal-time propagation)."""

    parent_column: str
    as_column: str


class ForeignKeyPlan(BaseModel):
    column: str
    parent_table: str
    parent_column: str
    relationship: str = "many_to_one"  # many_to_one | one_to_one
    # parent columns to gather with the SAME index as the FK key (e.g. order_ts)
    inherit: list[InheritPlan] = Field(default_factory=list)


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
    order = topo_sort(selected, [(r["child_table"], r["parent_table"]) for r in rels])

    plans: list[TablePlan] = []
    for tbl in order:
        meta = catalog.get_table(tbl)
        profile = catalog.get_latest_profile(tbl) or {}
        col_profiles = {c["name"]: c for c in profile.get("columns", [])}
        inherit_map = profile.get("inherit", {})
        fk_cols = {
            r["child_column"]: ForeignKeyPlan(
                column=r["child_column"],
                parent_table=r["parent_table"],
                parent_column=r["parent_column"],
                relationship=r.get("kind", "many_to_one"),
                inherit=(
                    [
                        InheritPlan(
                            parent_column=inherit_map[r["child_column"]]["parent_column"],
                            as_column=inherit_map[r["child_column"]]["as"],
                        )
                    ]
                    if r["child_column"] in inherit_map
                    else []
                ),
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


_CALENDAR_POLARS = {
    "day_of_week": lambda c: c.dt.weekday(),  # Mon=1..Sun=7
    "is_weekend": lambda c: c.dt.weekday() >= 6,
    "week": lambda c: c.dt.week(),
    "month": lambda c: c.dt.month(),
    "quarter": lambda c: c.dt.quarter(),
    "year": lambda c: c.dt.year(),
}


def _apply_calendar(
    df: pl.DataFrame, tp: TablePlan, cp: ColumnPlan, cfg: dict[str, Any]
) -> pl.DataFrame:
    """Derive a calendar attribute column from an anchor date/datetime column."""
    anchor, part = cfg["anchor"], cfg["part"]
    if anchor not in df.columns:
        raise GenerationError(
            f"calendar on {tp.name}.{cp.name}: anchor column {anchor!r} not found.",
            hint="Declare the anchor date column before the calendar column.",
        )
    if part in _CALENDAR_POLARS:  # vectorized fast path
        return df.with_columns(_CALENDAR_POLARS[part](pl.col(anchor)).alias(cp.name))
    from ai_data_platform.generator.seasonality import calendar_features

    feats = calendar_features(
        df.get_column(anchor).to_list(),
        [part],
        fiscal_year_start_month=int(cfg.get("fiscal_year_start_month", 1)),
        hemisphere=str(cfg.get("hemisphere", "north")),
        country=cfg.get("country"),
    )
    return df.with_columns(pl.Series(cp.name, feats[part]))


def _apply_seasonal_scale(
    df: pl.DataFrame, tp: TablePlan, cp: ColumnPlan, cfg: dict[str, Any]
) -> pl.DataFrame:
    """Multiply a base-sampled metric by the seasonal multiplier at its anchor date."""
    anchor = cfg["anchor"]
    if anchor not in df.columns:
        raise GenerationError(
            f"seasonal_scale on {tp.name}.{cp.name}: anchor column {anchor!r} not found.",
            hint="Declare the anchor date column before the scaled metric column.",
        )
    from ai_data_platform.generator.seasonality import multiplier_for

    mult = multiplier_for(df.get_column(anchor).to_list(), dict(cfg.get("factor", {})))
    return df.with_columns((pl.col(cp.name) * pl.Series(cp.name + "_m", mult)).alias(cp.name))


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
        if d.get("calendar"):
            df = _apply_calendar(df, tp, cp, d["calendar"])
        if d.get("seasonal_scale"):
            df = _apply_seasonal_scale(df, tp, cp, d["seasonal_scale"])
        if d.get("null_unless"):
            cond = _guarded_sql_expr(str(d["null_unless"]))
            df = df.with_columns(pl.when(cond).then(pl.col(cp.name)).otherwise(None).alias(cp.name))
    return df


def _build_chunk(
    plan: GenerationPlan,
    tp: TablePlan,
    chunk_idx: int,
    offset: int,
    n: int,
    key_pool: dict[tuple[str, str], pl.Series],
    o2o_perm: dict[str, np.ndarray],
) -> pl.DataFrame:
    """Build one chunk of `n` rows. RNG is consumed columns-then-FKs in declared
    order so output is byte-identical regardless of chunk size."""
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
        # carry parent columns into the child with the SAME idx (no RNG consumed)
        for inh in fk.inherit:
            parent_col = key_pool.get((fk.parent_table, inh.parent_column))
            if parent_col is None or len(parent_col) != len(pool):
                raise GenerationError(
                    f"Cannot inherit {fk.parent_table}.{inh.parent_column} into "
                    f"{tp.name}.{inh.as_column}: parent column not published.",
                    hint="The parent must generate this column in the same run; "
                    "declare `inherit` on the referencing column.",
                )
            data[inh.as_column] = pl.Series(parent_col.gather(idx))
    return _apply_derives(pl.DataFrame(data), tp, rng)


def _resolve_workers(parallel_workers: int) -> int:
    """0 = auto (min(cpu_count, 8)); 1 = disabled."""
    if parallel_workers <= 0:
        return min(os.cpu_count() or 1, 8)
    return max(1, parallel_workers)


def _chunk_specs(total_rows: int, chunk_rows: int) -> list[tuple[int, int, int]]:
    """Return (chunk_idx, offset, n) for each chunk in order."""
    specs: list[tuple[int, int, int]] = []
    remaining = total_rows
    chunk_idx = 0
    while True:
        n = min(remaining, chunk_rows) if remaining > 0 else 0
        offset = total_rows - remaining
        specs.append((chunk_idx, offset, n))
        remaining -= n
        chunk_idx += 1
        if remaining <= 0:
            break
    return specs


def generate(
    plan: GenerationPlan,
    output_dir: str | Path,
    *,
    output_format: str = "parquet",
    parallel_workers: int = 1,
) -> dict[str, Any]:
    """Execute a plan, streaming each chunk to disk. Returns {table: {rows, path}}.

    Peak memory is bounded to one chunk plus the parent key pools (only the
    key columns of already-generated tables), never a whole table.
    """
    key_pool: dict[tuple[str, str], pl.Series] = {}
    results: dict[str, Any] = {}

    # columns each parent must publish so children can inherit them (seasonal anchor carry)
    carry_cols: dict[str, set[str]] = {}
    for t in plan.tables:
        for fk in t.foreign_keys:
            for inh in fk.inherit:
                carry_cols.setdefault(fk.parent_table, set()).add(inh.parent_column)

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

        writer = ChunkWriter(tp.name, output_dir, output_format)
        key_cols = [cp.name for cp in tp.columns if cp.sampler in ("sequence", "uuid")]
        # also accumulate any columns children want to inherit (e.g. the seasonal anchor)
        accum_cols = list(dict.fromkeys(key_cols + sorted(carry_cols.get(tp.name, set()))))
        key_accum: dict[str, list[pl.Series]] = {c: [] for c in accum_cols}
        specs = _chunk_specs(tp.rows, plan.chunk_rows)
        workers = _resolve_workers(parallel_workers)

        if workers > 1 and len(specs) > 1:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        _build_chunk, plan, tp, idx, offset, n, key_pool, o2o_perm
                    ): idx
                    for idx, offset, n in specs
                }
                chunks_by_idx: dict[int, pl.DataFrame] = {}
                for fut in futures:
                    idx = futures[fut]
                    chunks_by_idx[idx] = fut.result()
            ordered = [chunks_by_idx[i] for i in range(len(specs))]
        else:
            ordered = [
                _build_chunk(plan, tp, idx, offset, n, key_pool, o2o_perm)
                for idx, offset, n in specs
            ]

        total = 0
        for chunk_df in ordered:
            writer.write_chunk(chunk_df)
            for c in accum_cols:
                if c in chunk_df.columns:
                    key_accum[c].append(chunk_df.get_column(c))
            total += len(chunk_df)
        path = writer.close()

        # register this table's key + carried columns for children
        for c in accum_cols:
            series = key_accum[c]
            if series:
                key_pool[(tp.name, c)] = pl.concat(series) if len(series) > 1 else series[0]
        results[tp.name] = {"rows": total, "path": str(path)}
        log.info("generated %s: %d rows -> %s", tp.name, total, path)
    return results
