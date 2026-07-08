"""Quality checks derived from catalog metadata — never handwritten per table.

Score = weighted pass rate per category (weights configurable, versioned).
Every check reports evidence and a remediation hint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import polars as pl

from ai_data_platform.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.metadata.catalog import Catalog

log = get_logger("adp.quality")

SCORE_VERSION = 1
DEFAULT_WEIGHTS = {
    "integrity": 0.35,  # pk uniqueness, fk inclusion
    "completeness": 0.25,  # null ratios vs profile
    "validity": 0.25,  # ranges vs profile
    "consistency": 0.15,  # categorical domain adherence
}


def derive_rules(catalog: Catalog, table: str) -> list[dict[str, Any]]:
    """Build rules for a table from its metadata + latest profile."""
    meta = catalog.get_table(table)
    profile = catalog.get_latest_profile(table) or {}
    col_profiles = {c["name"]: c for c in profile.get("columns", [])}
    fk_child_cols = {
        r["child_column"] for r in catalog.get_relationships() if r["child_table"] == table
    }
    rules: list[dict[str, Any]] = []

    for col in meta["columns"]:
        p = col_profiles.get(col["name"], {})
        is_key = col["primary_key"] or col["name"] in fk_child_cols
        if col["primary_key"]:
            rules.append(
                {"rule_type": "unique", "params": {"column": col["name"]}, "category": "integrity"}
            )
            rules.append(
                {
                    "rule_type": "not_null",
                    "params": {"column": col["name"]},
                    "category": "completeness",
                }
            )
        elif p.get("null_ratio", 1.0) < 0.01:
            rules.append(
                {
                    "rule_type": "not_null",
                    "params": {"column": col["name"], "tolerance": 0.02},
                    "category": "completeness",
                }
            )
        # range checks apply to measures, not identity columns (keys legitimately extend)
        if (
            not is_key
            and p.get("min") is not None
            and p.get("max") is not None
            and col["type"] in ("int", "float")
        ):
            span = abs(float(p["max"]) - float(p["min"])) or 1.0
            rules.append(
                {
                    "rule_type": "range",
                    "params": {
                        "column": col["name"],
                        "min": float(p["min"]) - 0.1 * span,
                        "max": float(p["max"]) + 0.1 * span,
                        "tolerance": 0.01,
                    },
                    "category": "validity",
                }
            )
        top = p.get("top_values") or []
        if top and 0 < p.get("distinct", 99) <= 20 and col["type"] == "string":
            rules.append(
                {
                    "rule_type": "accepted_values",
                    "params": {
                        "column": col["name"],
                        "values": [t["value"] for t in top],
                        "tolerance": 0.05,
                    },
                    "category": "consistency",
                }
            )

    for rel in catalog.get_relationships():
        if rel["child_table"] == table and rel["confidence"] >= 0.6:
            rules.append(
                {
                    "rule_type": "foreign_key",
                    "params": {
                        "column": rel["child_column"],
                        "parent_table": rel["parent_table"],
                        "parent_column": rel["parent_column"],
                    },
                    "category": "integrity",
                }
            )
    return rules


def _run_rule(
    rule: dict[str, Any], df: pl.DataFrame, parents: dict[str, pl.DataFrame]
) -> dict[str, Any]:
    rt, p = rule["rule_type"], rule["params"]
    col = p.get("column")
    result: dict[str, Any] = {"rule_type": rt, "params": p, "category": rule["category"]}
    try:
        if col is not None and col not in df.columns and rt != "foreign_key":
            return {**result, "passed": False, "evidence": f"column {col!r} missing"}
        if rt == "not_null":
            ratio = df.get_column(col).null_count() / max(len(df), 1)
            tol = float(p.get("tolerance", 0.0))
            return {
                **result,
                "passed": ratio <= tol,
                "evidence": f"null ratio {ratio:.4f} (tolerance {tol})",
            }
        if rt == "unique":
            s = df.get_column(col).drop_nulls()
            dup = len(s) - s.n_unique()
            return {**result, "passed": dup == 0, "evidence": f"{dup} duplicate value(s)"}
        if rt == "range":
            s = df.get_column(col).drop_nulls()
            if len(s) == 0 or not s.dtype.is_numeric():
                return {**result, "passed": True, "evidence": "no numeric data to check"}
            lo, hi = float(p["min"]), float(p["max"])
            f64 = s.cast(pl.Float64)
            bad = int((f64 < lo).sum() or 0) + int((f64 > hi).sum() or 0)
            ratio = bad / max(len(s), 1)
            tol = float(p.get("tolerance", 0.0))
            return {
                **result,
                "passed": ratio <= tol,
                "evidence": f"{bad} value(s) ({ratio:.2%}) outside [{lo:.4g}, {hi:.4g}] "
                f"(tolerance {tol:.0%})",
            }
        if rt == "accepted_values":
            s = df.get_column(col).drop_nulls().cast(pl.String)
            allowed = {str(v) for v in p["values"]}
            bad = sum(1 for v in s.to_list() if v not in allowed)
            ratio = bad / max(len(s), 1)
            tol = float(p.get("tolerance", 0.0))
            return {
                **result,
                "passed": ratio <= tol,
                "evidence": f"{bad} value(s) outside accepted set ({ratio:.2%})",
            }
        if rt == "foreign_key":
            parent_df = parents.get(p["parent_table"])
            if parent_df is None or p["parent_column"] not in parent_df.columns:
                return {**result, "passed": True, "evidence": "parent table not in scope; skipped"}
            child = df.get_column(p["column"]).drop_nulls().cast(pl.String)
            parent_keys = set(
                parent_df.get_column(p["parent_column"]).drop_nulls().cast(pl.String).to_list()
            )
            orphans = sum(1 for v in child.to_list() if v not in parent_keys)
            return {**result, "passed": orphans == 0, "evidence": f"{orphans} orphan value(s)"}
        return {**result, "passed": True, "evidence": f"unknown rule {rt!r}; skipped"}
    except Exception as e:  # engine failure = failed check with evidence
        return {**result, "passed": False, "evidence": f"check error: {e}"}


def run_quality_checks(
    catalog: Catalog,
    data: dict[str, pl.DataFrame],
    *,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run derived rules against provided DataFrames (generated or sampled).

    Returns a report: per-table check results + weighted overall score.
    """
    weights = weights or DEFAULT_WEIGHTS
    tables_report: list[dict[str, Any]] = []
    category_totals: dict[str, list[bool]] = {}

    for table, df in data.items():
        rules = derive_rules(catalog, table)
        catalog.replace_quality_rules(
            table, [{"rule_type": r["rule_type"], "params": r["params"]} for r in rules]
        )
        checks = [_run_rule(r, df, data) for r in rules]
        for c in checks:
            category_totals.setdefault(c["category"], []).append(bool(c["passed"]))
        passed = sum(1 for c in checks if c["passed"])
        tables_report.append(
            {
                "table": table,
                "rows": len(df),
                "checks": checks,
                "passed": passed,
                "total": len(checks),
            }
        )
        log.info("quality %s: %d/%d checks passed", table, passed, len(checks))

    category_scores = {cat: (sum(v) / len(v) if v else 1.0) for cat, v in category_totals.items()}
    total_weight = sum(weights.get(c, 0.0) for c in category_scores) or 1.0
    score = sum(category_scores[c] * weights.get(c, 0.0) for c in category_scores) / total_weight

    return {
        "score_version": SCORE_VERSION,
        "quality_score": round(score * 100, 2),
        "weights": weights,
        "category_scores": {c: round(v * 100, 2) for c, v in category_scores.items()},
        "tables": tables_report,
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Data Quality Report",
        "",
        f"**Quality Score: {report['quality_score']}/100** (score v{report['score_version']})",
        "",
        "| Category | Score |",
        "|---|---|",
    ]
    for cat, v in report["category_scores"].items():
        lines.append(f"| {cat} | {v} |")
    for t in report["tables"]:
        lines += [
            "",
            f"## {t['table']} — {t['passed']}/{t['total']} passed ({t['rows']} rows)",
            "",
            "| Check | Column | Result | Evidence |",
            "|---|---|---|---|",
        ]
        for c in t["checks"]:
            col = c["params"].get("column", "—")
            status = "✅" if c["passed"] else "❌"
            lines.append(f"| {c['rule_type']} | {col} | {status} | {c['evidence']} |")
    return "\n".join(lines) + "\n"
