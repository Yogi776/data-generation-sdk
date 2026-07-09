"""Static complexity analysis of a GenerationPlan.

Classifies per-column generation cost and emits a module-level complexity table
plus hot-spot warnings grounded in how the engine actually executes (see the
performance audit). No measurement — purely structural.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.generator.engine import ColumnPlan, GenerationPlan

# samplers whose per-row work is pure-Python (holds the GIL, limits thread scaling)
_PY_STRING_SAMPLERS = {
    "uuid", "template", "full_name", "email", "phone", "address", "words", "choice",
}
_NUMPY_SAMPLERS = {"sequence", "lognormal", "normal", "uniform_int", "poisson", "bool"}

# static per-module complexity (time/space) for the documented pipeline
MODULE_COMPLEXITY: list[dict[str, str]] = [
    {"module": "generation (numeric)", "time": "O(rows)", "space": "O(chunk)", "note": "numpy-vectorized, GIL-releasing"},
    {"module": "generation (string)", "time": "O(rows)", "space": "O(chunk)", "note": "per-row Python; GIL-bound (Phase 3)"},
    {"module": "FK resolution", "time": "O(rows)", "space": "O(parent keys)", "note": "vectorized gather; key_pool retained"},
    {"module": "seasonality", "time": "O(days)+O(rows)", "space": "O(days)", "note": "curve O(days); sampling O(rows)"},
    {"module": "write (parquet/csv)", "time": "O(rows)", "space": "O(chunk)", "note": "streaming row-group per chunk"},
    {"module": "validation (DuckDB)", "time": "O(rows) scan", "space": "O(1)", "note": "aggregate SQL, streaming"},
    {"module": "profiling (source)", "time": "O(sample)", "space": "O(file)", "note": "full-file load then sample (Phase 3)"},
    {"module": "query/export", "time": "O(scan)", "space": "O(result)", "note": "pushdown + LIMIT/scan-guard"},
]


def _col_cost(cp: ColumnPlan) -> str:
    if cp.sampler in _NUMPY_SAMPLERS:
        return "O(rows) vectorized"
    if cp.sampler in _PY_STRING_SAMPLERS:
        return "O(rows) python-string"
    if cp.sampler in ("date", "datetime", "seasonal_date", "seasonal_datetime"):
        return "O(rows) python-datetime"
    return "O(rows)"


def analyze_complexity(plan: GenerationPlan) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    warnings: list[str] = []
    for tp in plan.tables:
        py_string = [cp.name for cp in tp.columns if cp.sampler in _PY_STRING_SAMPLERS]
        has_conditional = any(
            (cp.derive or {}).get("conditional") for cp in tp.columns
        )
        tables.append(
            {
                "table": tp.name,
                "rows": tp.rows,
                "columns": len(tp.columns),
                "foreign_keys": len(tp.foreign_keys),
                "python_string_columns": py_string,
                "column_costs": {cp.name: _col_cost(cp) for cp in tp.columns},
            }
        )
        if py_string and tp.rows >= 10_000_000:
            warnings.append(
                f"{tp.name}: {len(py_string)} per-row Python string sampler(s) "
                f"({', '.join(py_string[:4])}{'…' if len(py_string) > 4 else ''}) are GIL-bound "
                "and cap thread scaling at scale (Phase 3: vectorize)."
            )
        if has_conditional and tp.rows >= 10_000_000:
            warnings.append(
                f"{tp.name}: values_by/conditional derive uses an O(rows) Python scatter "
                "(Phase 3: vectorize)."
            )
    return {"modules": MODULE_COMPLEXITY, "tables": tables, "warnings": warnings}
