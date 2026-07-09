"""Seasonality validation — does generated data follow the declared factor curve?

Reads each table's `profile["seasonality"]` marker, aggregates the anchor column
over time via DuckDB (no full-table load), and scores five generic metrics
against the expected curve: weekly pattern, event spikes, trend, expected/observed
correlation, and cross-table peak alignment (the propagation guarantee).

Kept separate from `quality/checks.py` so its category weights stay independent.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import numpy as np

from ai_data_platform.core.logging import get_logger
from ai_data_platform.generator.seasonality import _range_dates, _to_date, build_day_weights
from ai_data_platform.quality.duckdb_checks import (
    _discover_data_files,
    _quote_ident,
    _register_table,
)

if TYPE_CHECKING:  # pragma: no cover
    from datetime import date

    from ai_data_platform.metadata.catalog import Catalog

log = get_logger("adp.quality.seasonality")

SEASONALITY_SCORE_VERSION = 1
DEFAULT_WEIGHTS = {
    "correlation": 0.35,  # expected vs observed daily density
    "weekly": 0.20,  # day-of-week profile
    "events": 0.20,  # promotion/holiday spikes present
    "trend": 0.15,  # growth direction
    "cross_table": 0.10,  # parents & children peak together
}
_DOW_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DOW_INDEX = {n.lower(): i for i, n in enumerate(_DOW_ORDER)}
_TOP_K = 10


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _observed_daily(
    con: duckdb.DuckDBPyConnection, table: str, anchor: str, start: date, end: date
) -> np.ndarray:
    """Row counts per day over [start, end], aligned to build_day_weights order."""
    tq, aq = _quote_ident(table), _quote_ident(anchor)
    rows = con.execute(
        f"SELECT CAST({aq} AS DATE) d, COUNT(*) c FROM {tq} "
        f"WHERE {aq} IS NOT NULL GROUP BY 1"
    ).fetchall()
    counts = {r[0]: int(r[1]) for r in rows}
    return np.array([counts.get(d, 0) for d in _range_dates(start, end)], dtype=float)


def _anchor_of(profile: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    for c in profile.get("columns", []):
        if c.get("seasonality"):
            return c["name"], c["seasonality"].get("factor", {})
    return None


def _seasonal_range(factor: dict[str, Any], observed_min: Any, observed_max: Any) -> tuple[date, date]:
    start = _to_date(factor.get("_start") or observed_min)
    end = _to_date(factor.get("_end") or observed_max)
    return start, end


def _weekly_check(observed: np.ndarray, days: list[date], factor: dict[str, Any]) -> dict[str, Any]:
    weekly = factor.get("weekly") or {}
    dow = np.array([d.weekday() for d in days])
    obs = np.array([observed[dow == k].mean() if (dow == k).any() else 0.0 for k in range(7)])
    exp = np.ones(7)
    for name, mult in weekly.items():
        key = str(name).strip().lower()
        if key in _DOW_INDEX:
            exp[_DOW_INDEX[key]] = float(mult)
    r = _pearson(obs, exp)
    peak = _DOW_ORDER[int(np.argmax(obs))]
    return {
        "metric": "weekly_pattern",
        "category": "weekly",
        "passed": r >= 0.6,
        "value": round(r, 3),
        "evidence": f"day-of-week r={r:.2f} vs declared weights; busiest={peak}",
    }


def _event_checks(
    observed: np.ndarray, days: list[date], factor: dict[str, Any]
) -> list[dict[str, Any]]:
    events = factor.get("events") or []
    if not events:
        return []
    baseline = float(np.median(observed)) or 1.0
    out: list[dict[str, Any]] = []
    for ev in events:
        lo, hi = _to_date(ev["start"]), _to_date(ev["end"])
        mask = np.array([lo <= d <= hi for d in days])
        if not mask.any():
            continue
        ratio = float(observed[mask].mean() / baseline)
        expected = float(ev.get("multiplier", 1.0))
        out.append(
            {
                "metric": f"event:{ev.get('name', 'window')}",
                "category": "events",
                "passed": ratio >= max(1.0, 0.5 * expected),
                "value": round(ratio, 2),
                "evidence": f"{ratio:.1f}x baseline in window (declared {expected:.1f}x)",
            }
        )
    return out


def _trend_check(observed: np.ndarray, factor: dict[str, Any]) -> dict[str, Any] | None:
    trend = factor.get("trend") or {}
    growth = float(trend.get("annual_growth", trend.get("rate", 0.0)))
    if growth == 0:
        return None
    x = np.arange(len(observed), dtype=float)
    slope = float(np.polyfit(x, observed, 1)[0]) if len(observed) >= 2 else 0.0
    ok = (slope > 0) == (growth > 0)
    return {
        "metric": "trend_direction",
        "category": "trend",
        "passed": bool(ok),
        "value": round(slope, 5),
        "evidence": f"daily-count slope {slope:+.4f} vs declared growth {growth:+.2f}/yr",
    }


def _correlation_check(
    observed: np.ndarray, start: date, end: date, factor: dict[str, Any]
) -> dict[str, Any]:
    expected = build_day_weights(start, end, factor)
    obs = observed / (observed.sum() or 1.0)
    r = _pearson(obs, expected)
    return {
        "metric": "curve_correlation",
        "category": "correlation",
        "passed": r >= 0.7,
        "value": round(r, 3),
        "evidence": f"expected-vs-observed daily density r={r:.2f}",
    }


def build_seasonality_report(
    catalog: Catalog,
    data_dir: str | Path,
    *,
    tables: list[str] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Validate observed seasonality against the declared factor curve per table."""
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
    tables_report: list[dict[str, Any]] = []
    cross_table: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    category_totals: dict[str, list[bool]] = {}
    # remember each seasonal table's observed daily curve for cross-table checks
    seasonal_daily: dict[str, tuple[np.ndarray, list[date], str]] = {}
    try:
        for table, fpath in files.items():
            _register_table(con, table, fpath)

        selected = sorted(t for t in files if (tables is None or t in tables))
        for table in selected:
            profile = catalog.get_latest_profile(table) or {}
            anchor_info = _anchor_of(profile)
            if not anchor_info:
                continue
            anchor, factor = anchor_info
            aq, tq = _quote_ident(anchor), _quote_ident(table)
            row = con.execute(
                f"SELECT MIN(CAST({aq} AS DATE)), MAX(CAST({aq} AS DATE)) FROM {tq}"
            ).fetchone()
            mn, mx = (row[0], row[1]) if row else (None, None)
            start, end = _seasonal_range(factor, mn, mx)
            days = _range_dates(start, end)
            observed = _observed_daily(con, table, anchor, start, end)
            seasonal_daily[table] = (observed, days, anchor)

            checks: list[dict[str, Any]] = [
                _correlation_check(observed, start, end, factor),
                _weekly_check(observed, days, factor),
            ]
            trend = _trend_check(observed, factor)
            if trend:
                checks.append(trend)
            checks.extend(_event_checks(observed, days, factor))

            for c in checks:
                category_totals.setdefault(c["category"], []).append(bool(c["passed"]))
            passed = sum(1 for c in checks if c["passed"])
            tables_report.append(
                {
                    "table": table,
                    "anchor": anchor,
                    "checks": checks,
                    "passed": passed,
                    "total": len(checks),
                }
            )
            expected = build_day_weights(start, end, factor)
            obs_norm = observed / (observed.sum() or 1.0)
            daily.extend(
                {
                    "table": table,
                    "date": d.isoformat(),
                    "observed_count": int(observed[i]),
                    "expected_intensity": round(float(expected[i]), 8),
                    "observed_intensity": round(float(obs_norm[i]), 8),
                }
                for i, d in enumerate(days)
            )
            log.info("seasonality %s: %d/%d checks passed", table, passed, len(checks))

        # cross-table: a child that inherits a parent's seasonal anchor should peak with it
        rel_by_child: dict[str, list[dict[str, Any]]] = {}
        for r in catalog.get_relationships():
            rel_by_child.setdefault(r["child_table"], []).append(r)
        for child in selected:
            profile = catalog.get_latest_profile(child) or {}
            inherit = profile.get("inherit", {})
            for fk_col, m in inherit.items():
                parent = next(
                    (
                        r["parent_table"]
                        for r in rel_by_child.get(child, [])
                        if r["child_column"] == fk_col
                    ),
                    None,
                )
                if parent not in seasonal_daily:
                    continue
                parent_obs, parent_days, _ = seasonal_daily[parent]
                local = m["as"]
                if local not in {c[0] for c in con.execute(f"DESCRIBE {_quote_ident(child)}").fetchall()}:
                    continue
                child_obs = _observed_daily(
                    con, child, local, parent_days[0], parent_days[-1]
                )
                jac = _jaccard_top_days(parent_obs, child_obs, parent_days)
                corr = _pearson(
                    parent_obs / (parent_obs.sum() or 1.0),
                    child_obs / (child_obs.sum() or 1.0),
                )
                ok = jac >= 0.6 or corr >= 0.7
                category_totals.setdefault("cross_table", []).append(ok)
                cross_table.append(
                    {
                        "child": child,
                        "parent": parent,
                        "inherited": local,
                        "passed": ok,
                        "peak_overlap": round(jac, 2),
                        "correlation": round(corr, 3),
                        "evidence": f"{child} shares {jac:.0%} of top-{_TOP_K} peak days with "
                        f"{parent} (r={corr:.2f})",
                    }
                )
    finally:
        con.close()

    category_scores = {c: (sum(v) / len(v) if v else 1.0) for c, v in category_totals.items()}
    total_weight = sum(weights.get(c, 0.0) for c in category_scores) or 1.0
    score = sum(category_scores[c] * weights.get(c, 0.0) for c in category_scores) / total_weight

    return {
        "score_version": SEASONALITY_SCORE_VERSION,
        "seasonality_score": round(score * 100, 2),
        "weights": weights,
        "category_scores": {c: round(v * 100, 2) for c, v in category_scores.items()},
        "tables": tables_report,
        "cross_table": cross_table,
        "daily": daily,
        "engine": "duckdb",
    }


def _jaccard_top_days(a: np.ndarray, b: np.ndarray, days: list[date]) -> float:
    if a.sum() == 0 or b.sum() == 0:
        return 0.0
    top_a = {days[i] for i in np.argsort(a)[-_TOP_K:]}
    top_b = {days[i] for i in np.argsort(b)[-_TOP_K:]}
    union = top_a | top_b
    return len(top_a & top_b) / len(union) if union else 0.0


def seasonality_report_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Seasonality Validation Report",
        "",
        f"**Seasonality Score: {report['seasonality_score']}/100** "
        f"(v{report['score_version']})",
        "",
        "| Category | Score |",
        "|---|---|",
    ]
    for cat, v in report["category_scores"].items():
        lines.append(f"| {cat} | {v} |")
    for t in report["tables"]:
        lines += [
            "",
            f"## {t['table']} (anchor: `{t['anchor']}`) — {t['passed']}/{t['total']} passed",
            "",
            "| Metric | Result | Value | Evidence |",
            "|---|---|---|---|",
        ]
        for c in t["checks"]:
            status = "✅" if c["passed"] else "❌"
            lines.append(f"| {c['metric']} | {status} | {c['value']} | {c['evidence']} |")
    if report["cross_table"]:
        lines += [
            "",
            "## Cross-table propagation",
            "",
            "| Child | Parent | Result | Peak overlap | Evidence |",
            "|---|---|---|---|---|",
        ]
        for x in report["cross_table"]:
            status = "✅" if x["passed"] else "❌"
            lines.append(
                f"| {x['child']} | {x['parent']} | {status} | {x['peak_overlap']} | {x['evidence']} |"
            )
    return "\n".join(lines) + "\n"


def seasonality_daily_csv(report: dict[str, Any]) -> str:
    """CSV of per-day observed vs expected intensity — feed a charting tool."""
    header = "table,date,observed_count,expected_intensity,observed_intensity"
    rows = [
        f"{d['table']},{d['date']},{d['observed_count']},"
        f"{d['expected_intensity']},{d['observed_intensity']}"
        for d in report["daily"]
    ]
    return "\n".join([header, *rows]) + "\n"
