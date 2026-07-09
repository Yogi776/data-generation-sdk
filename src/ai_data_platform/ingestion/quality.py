"""Data quality validator.

Derives warnings purely from the computed profile — no domain assumptions — so
it works for any industry. Each warning has a stable ``code``, a ``severity``
(info | warning | high), the affected ``column`` (or null for table-level), and a
human ``message``.
"""

from __future__ import annotations

from typing import Any

# Thresholds (tunable via options["quality"]).
_DEFAULTS = {
    "high_null_pct": 50.0,
    "some_null_pct": 5.0,
    "high_cardinality_ratio": 0.9,  # distinct/rows above this on a non-id column
    "low_cardinality_max": 1,  # distinct <= this => constant
}


def evaluate(profile: dict[str, Any], *, thresholds: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    t = {**_DEFAULTS, **(thresholds or {})}
    warnings: list[dict[str, Any]] = []
    row_count = profile.get("row_count", 0)
    columns: dict[str, Any] = profile.get("columns", {})

    if row_count == 0:
        warnings.append(_w("empty_table", "high", None, "Source has zero rows."))
        return warnings

    dup = profile.get("duplicate_rows")
    if dup:
        pct = round(100.0 * dup / row_count, 2)
        warnings.append(
            _w("duplicate_rows", "warning" if pct < 10 else "high", None,
               f"{dup} duplicate row(s) ({pct}% of the table).")
        )

    for name, c in columns.items():
        null_pct = c.get("null_percentage") or 0.0
        distinct = c.get("distinct")
        if null_pct >= t["high_null_pct"]:
            warnings.append(_w("high_null", "high", name, f"{null_pct:.1f}% null."))
        elif null_pct >= t["some_null_pct"]:
            warnings.append(_w("some_null", "warning", name, f"{null_pct:.1f}% null."))

        if distinct is not None:
            if distinct <= t["low_cardinality_max"] and row_count > 1:
                warnings.append(
                    _w("constant_column", "warning", name,
                       f"Only {distinct} distinct value(s) — column may be constant.")
                )
            elif (
                not _looks_id(name)
                and row_count > 100
                and distinct / row_count >= t["high_cardinality_ratio"]
            ):
                warnings.append(
                    _w("high_cardinality", "info", name,
                       "Nearly unique values — likely a free-text or identifier field.")
                )

        # Numeric sanity: min == max (no variance).
        mn, mx = c.get("min"), c.get("max")
        if mn is not None and mx is not None and mn == mx and (distinct or 0) > 0:
            warnings.append(
                _w("no_variance", "info", name, f"min == max ({mn}) — no variance.")
            )

    return warnings


def _looks_id(name: str) -> bool:
    n = name.lower()
    return n == "id" or n.endswith("_id") or n.endswith("_key") or n.startswith("id_")


def _w(code: str, severity: str, column: str | None, message: str) -> dict[str, Any]:
    return {"code": code, "severity": severity, "column": column, "message": message}
