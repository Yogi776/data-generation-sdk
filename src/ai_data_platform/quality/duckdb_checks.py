"""DuckDB-backed quality checks — stream parquet/csv without loading full tables."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

from ai_data_platform.core.logging import get_logger
from ai_data_platform.quality.checks import (
    DEFAULT_WEIGHTS,
    SCORE_VERSION,
    derive_rules,
)

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.metadata.catalog import Catalog

log = get_logger("adp.quality.duckdb")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _register_table(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> None:
    q = _quote_ident(table)
    p = _sql_string_literal(str(path))
    if path.suffix == ".parquet":
        con.execute(f"CREATE OR REPLACE VIEW {q} AS SELECT * FROM read_parquet({p})")
    elif path.suffix == ".csv":
        con.execute(f"CREATE OR REPLACE VIEW {q} AS SELECT * FROM read_csv_auto({p}, header=true)")
    else:
        raise ValueError(f"unsupported format for {path}")


def _discover_data_files(data_dir: Path, known: set[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for pattern in ("*.parquet", "*.csv"):
        for f in sorted(data_dir.glob(pattern)):
            if f.stem in known and f.stem not in out:
                out[f.stem] = f
    return out


def _run_rule_sql(
    con: duckdb.DuckDBPyConnection,
    rule: dict[str, Any],
    table: str,
    parents: set[str],
) -> dict[str, Any]:
    rt, p = rule["rule_type"], rule["params"]
    col = p.get("column")
    tq = _quote_ident(table)
    result: dict[str, Any] = {"rule_type": rt, "params": p, "category": rule["category"]}
    try:
        if col is not None and rt != "foreign_key":
            cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {tq}").fetchall()}
            if col not in cols:
                return {**result, "passed": False, "evidence": f"column {col!r} missing"}

        if rt == "not_null":
            ratio = float(
                con.execute(
                    f"SELECT COALESCE(AVG(CASE WHEN {_quote_ident(col)} IS NULL THEN 1.0 ELSE 0.0 END), 0) "
                    f"FROM {tq}"
                ).fetchone()[0]
            )
            tol = float(p.get("tolerance", 0.0))
            return {
                **result,
                "passed": ratio <= tol,
                "evidence": f"null ratio {ratio:.4f} (tolerance {tol})",
            }

        if rt == "unique":
            row = con.execute(
                f"SELECT COUNT(*) - COUNT(DISTINCT {_quote_ident(col)}) FROM {tq} "
                f"WHERE {_quote_ident(col)} IS NOT NULL"
            ).fetchone()
            dup = int(row[0])
            return {**result, "passed": dup == 0, "evidence": f"{dup} duplicate value(s)"}

        if rt == "range":
            lo, hi = float(p["min"]), float(p["max"])
            cq = _quote_ident(col)
            row = con.execute(
                f"SELECT COUNT(*) FROM {tq} WHERE {cq} IS NOT NULL "
                f"AND (CAST({cq} AS DOUBLE) < ? OR CAST({cq} AS DOUBLE) > ?)",
                [lo, hi],
            ).fetchone()
            total = int(
                con.execute(f"SELECT COUNT(*) FROM {tq} WHERE {cq} IS NOT NULL").fetchone()[0]
            )
            bad = int(row[0])
            ratio = bad / max(total, 1)
            tol = float(p.get("tolerance", 0.0))
            return {
                **result,
                "passed": ratio <= tol,
                "evidence": f"{bad} value(s) ({ratio:.2%}) outside [{lo:.4g}, {hi:.4g}] "
                f"(tolerance {tol:.0%})",
            }

        if rt == "accepted_values":
            cq = _quote_ident(col)
            allowed = [str(v) for v in p["values"]]
            placeholders = ", ".join("?" for _ in allowed)
            row = con.execute(
                f"SELECT COUNT(*) FROM {tq} WHERE {cq} IS NOT NULL "
                f"AND CAST({cq} AS VARCHAR) NOT IN ({placeholders})",
                allowed,
            ).fetchone()
            total = int(
                con.execute(f"SELECT COUNT(*) FROM {tq} WHERE {cq} IS NOT NULL").fetchone()[0]
            )
            bad = int(row[0])
            ratio = bad / max(total, 1)
            tol = float(p.get("tolerance", 0.0))
            return {
                **result,
                "passed": ratio <= tol,
                "evidence": f"{bad} value(s) outside accepted set ({ratio:.2%})",
            }

        if rt == "foreign_key":
            parent = p["parent_table"]
            if parent not in parents:
                return {**result, "passed": True, "evidence": "parent table not in scope; skipped"}
            pq, ppq = _quote_ident(parent), _quote_ident(p["parent_column"])
            cq = _quote_ident(p["column"])
            row = con.execute(
                f"SELECT COUNT(*) FROM {tq} c WHERE c.{cq} IS NOT NULL "
                f"AND CAST(c.{cq} AS VARCHAR) NOT IN "
                f"(SELECT CAST({ppq} AS VARCHAR) FROM {pq} WHERE {ppq} IS NOT NULL)"
            ).fetchone()
            orphans = int(row[0])
            return {**result, "passed": orphans == 0, "evidence": f"{orphans} orphan value(s)"}

        return {**result, "passed": True, "evidence": f"unknown rule {rt!r}; skipped"}
    except Exception as e:
        return {**result, "passed": False, "evidence": f"check error: {e}"}


def run_quality_checks_on_dir(
    catalog: Catalog,
    data_dir: str | Path,
    *,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run derived rules against parquet/csv files via DuckDB (no full-table load)."""
    weights = weights or DEFAULT_WEIGHTS
    path = Path(data_dir)
    known = {t["table"] for t in catalog.list_tables()}
    files = _discover_data_files(path, known)
    if not files:
        from ai_data_platform.core.exceptions import GenerationError

        raise GenerationError(
            f"No generated csv/parquet files matching catalog tables in {path}.",
            hint="Run `adp generate-data` first, or pass data_dir.",
        )

    con = duckdb.connect()
    try:
        for table, fpath in files.items():
            _register_table(con, table, fpath)

        tables_report: list[dict[str, Any]] = []
        category_totals: dict[str, list[bool]] = {}
        registered = set(files)

        for table in sorted(files):
            rules = derive_rules(catalog, table)
            catalog.replace_quality_rules(
                table, [{"rule_type": r["rule_type"], "params": r["params"]} for r in rules]
            )
            checks = [_run_rule_sql(con, r, table, registered) for r in rules]
            for c in checks:
                category_totals.setdefault(c["category"], []).append(bool(c["passed"]))
            passed = sum(1 for c in checks if c["passed"])
            row_count = int(con.execute(f"SELECT COUNT(*) FROM {_quote_ident(table)}").fetchone()[0])
            tables_report.append(
                {
                    "table": table,
                    "rows": row_count,
                    "checks": checks,
                    "passed": passed,
                    "total": len(checks),
                }
            )
            log.info("quality %s: %d/%d checks passed", table, passed, len(checks))
    finally:
        con.close()

    category_scores = {cat: (sum(v) / len(v) if v else 1.0) for cat, v in category_totals.items()}
    total_weight = sum(weights.get(c, 0.0) for c in category_scores) or 1.0
    score = sum(category_scores[c] * weights.get(c, 0.0) for c in category_scores) / total_weight

    return {
        "score_version": SCORE_VERSION,
        "quality_score": round(score * 100, 2),
        "weights": weights,
        "category_scores": {c: round(v * 100, 2) for c, v in category_scores.items()},
        "tables": tables_report,
        "engine": "duckdb",
    }
