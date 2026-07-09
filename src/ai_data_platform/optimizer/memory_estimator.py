"""Memory estimation for a GenerationPlan.

Models what the engine *actually* does today: `generate()` materializes every
chunk of a table into an `ordered` list before writing (both the serial and the
ThreadPool paths), so per-table peak is whole-table, not one chunk. On top of
that, `key_pool` retains the key + inherited columns of every generated table for
the whole run, and each one_to_one FK holds a parent-length permutation array.

All heuristics, no measurement — enough to size a run and flag risk before it
starts. Pure functions over the Plan-IR (JSON-safe).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.generator.engine import ColumnPlan, GenerationPlan, TablePlan

# polars/arrow buffers + intermediate derive allocations roughly double the
# nominal column payload during a chunk build.
OVERHEAD = 2.0
_DEFAULT_STR = 16
_FK_DEFAULT = 36  # unknown FK key assumed uuid-shaped


def column_bytes(cp: ColumnPlan) -> int:
    """Estimated in-memory bytes per row for one sampled column."""
    p = cp.params
    match cp.sampler:
        case "sequence" | "lognormal" | "normal" | "uniform_int" | "poisson" | "datetime" | "seasonal_datetime":
            return 8
        case "date" | "seasonal_date":
            return 4
        case "bool":
            return 1
        case "uuid":
            return 36
        case "full_name":
            return 14
        case "email":
            return 26
        case "phone":
            return 15
        case "address":
            return 30
        case "city" | "country":
            return 10
        case "words":
            return 6 * int(p.get("k", 2)) + 1
        case "template":
            return max(len(str(p.get("pattern", "########"))), 4)
        case "choice":
            vals = p.get("values") or []
            if vals and all(isinstance(v, (int, float)) for v in vals):
                return 8
            avg = sum(len(str(v)) for v in vals) / len(vals) if vals else _DEFAULT_STR
            return max(int(avg), 1)
        case _:
            return _DEFAULT_STR


def _bytes_by_table(plan: GenerationPlan) -> dict[str, dict[str, int]]:
    """(table -> col -> bytes) for sampled columns, so children can look up
    parent key/inherited-column widths (plan is parents-first)."""
    out: dict[str, dict[str, int]] = {}
    for tp in plan.tables:
        out[tp.name] = {cp.name: column_bytes(cp) for cp in tp.columns}
    return out


def table_row_bytes(tp: TablePlan, by_table: dict[str, dict[str, int]]) -> int:
    """Bytes per row for a table incl. FK and inherited columns."""
    total = sum(by_table[tp.name].values())
    for fk in tp.foreign_keys:
        parent = by_table.get(fk.parent_table, {})
        total += parent.get(fk.parent_column, _FK_DEFAULT)
        for inh in fk.inherit:
            total += parent.get(inh.parent_column, 8)
    return total


def _children_by_parent(plan: GenerationPlan) -> set[str]:
    parents: set[str] = set()
    for tp in plan.tables:
        for fk in tp.foreign_keys:
            parents.add(fk.parent_table)
    return parents


def estimate_memory(
    plan: GenerationPlan, *, workers: int = 1
) -> dict[str, Any]:
    """Estimate peak RSS (MB) and the dominant contributor for a plan run."""
    by_table = _bytes_by_table(plan)
    parents = _children_by_parent(plan)

    per_table: list[dict[str, Any]] = []
    largest_table_mb = 0.0
    largest_table = None
    key_pool_bytes = 0
    o2o_bytes = 0

    for tp in plan.tables:
        row_bytes = table_row_bytes(tp, by_table)
        # engine holds the whole table (all chunks in `ordered`) before writing
        table_mb = row_bytes * tp.rows * OVERHEAD / 1e6
        per_table.append(
            {
                "table": tp.name,
                "rows": tp.rows,
                "row_bytes": row_bytes,
                "est_mb": round(table_mb, 2),
            }
        )
        if table_mb > largest_table_mb:
            largest_table_mb, largest_table = table_mb, tp.name

        # key_pool retains key (sequence/uuid) + carried columns for the whole run
        if tp.name in parents:
            carry = {
                inh.parent_column
                for other in plan.tables
                for fk in other.foreign_keys
                if fk.parent_table == tp.name
                for inh in fk.inherit
            }
            key_cols = [cp for cp in tp.columns if cp.sampler in ("sequence", "uuid")]
            retained = sum(column_bytes(cp) for cp in key_cols)
            retained += sum(by_table[tp.name].get(c, 8) for c in carry)
            key_pool_bytes += retained * tp.rows

        for fk in tp.foreign_keys:
            if fk.relationship == "one_to_one":
                o2o_bytes += 8 * next(
                    (t.rows for t in plan.tables if t.name == fk.parent_table), 0
                )

    peak_mb = largest_table_mb + (key_pool_bytes + o2o_bytes) / 1e6
    contributors = {
        "largest_table_mb": round(largest_table_mb, 2),
        "key_pool_mb": round(key_pool_bytes / 1e6, 2),
        "o2o_perm_mb": round(o2o_bytes / 1e6, 2),
    }
    dominant = max(contributors, key=lambda k: contributors[k])
    return {
        "peak_mb": round(peak_mb, 2),
        "largest_table": largest_table,
        "contributors": contributors,
        "dominant": dominant,
        "per_table": per_table,
        "overhead_factor": OVERHEAD,
    }
