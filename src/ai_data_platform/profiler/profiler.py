"""Table/column profiling with Polars.

Per column: row count, nulls, distinct, min/max/mean/std, top values,
type detection, PII classification, PK candidacy. Per table: PK candidates,
FK candidate confirmation (inclusion dependency on samples).

Every inference carries confidence + evidence — never a bare verdict.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

import polars as pl

from ai_data_platform.connectors.base import SampleBudget, TableSchema
from ai_data_platform.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import ProjectConfig
    from ai_data_platform.metadata.catalog import Catalog

log = get_logger("adp.profile")

TOP_VALUES_K = 10
PK_UNIQUENESS_THRESHOLD = 0.999
FK_INCLUSION_THRESHOLD = 0.95

# --- PII detection (three signals: name pattern, value regex, shape) ---------
_PII_NAME_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"(?i)e?[-_]?mail"),
    "phone": re.compile(r"(?i)phone|mobile|cell"),
    "name": re.compile(r"(?i)(^|_)(first|last|full|middle|customer|patient|user)?_?name$"),
    "ssn": re.compile(r"(?i)ssn|social_sec"),
    "dob": re.compile(r"(?i)dob|birth"),
    "address": re.compile(r"(?i)address|street|zip|postal"),
    "credit_card": re.compile(r"(?i)card_?(number|num|no)|cc_?num"),
    "ip_address": re.compile(r"(?i)ip_?addr"),
}
_PII_VALUE_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"^[\w.+-]+@[\w-]+\.[\w.]+$"),
    "phone": re.compile(r"^\+?[\d\s().-]{7,17}$"),
    "ssn": re.compile(r"^\d{3}-\d{2}-\d{4}$"),
    "credit_card": re.compile(r"^\d{13,19}$"),
    "ip_address": re.compile(r"^\d{1,3}(\.\d{1,3}){3}$"),
}
# date/datetime-shaped values are never phone/ssn evidence (false-positive guard)
_DATE_SHAPED = re.compile(r"^\d{4}-\d{2}-\d{2}([ T].*)?$")


def _luhn_ok(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


_NONPERSON_NAME = re.compile(
    r"(?i)(product|item|company|brand|store|file|table|column|category|plan|model)_?name$"
)


def classify_pii(
    name: str, values: list[str], *, numeric: bool = False
) -> tuple[str, str | None, float]:
    """Return (level, category, confidence). Levels: none | possible | likely.

    Numeric columns are exempt from value-pattern signals (amounts are not
    phone numbers); non-person *_name columns (product_name…) are exempt from
    the person-name signal.
    """
    name_hit = next((cat for cat, pat in _PII_NAME_PATTERNS.items() if pat.search(name)), None)
    if name_hit == "name" and _NONPERSON_NAME.search(name):
        name_hit = None
    if numeric:
        if name_hit:
            return "possible", name_hit, 0.5
        return "none", None, 0.9
    value_hit: str | None = None
    hit_ratio = 0.0
    sample = [v for v in values if v][:200]
    if sample and sum(1 for v in sample if _DATE_SHAPED.match(v.strip())) / len(sample) >= 0.6:
        sample = []  # date-shaped column: exempt from value-pattern PII signals
    if sample:
        for cat, pat in _PII_VALUE_PATTERNS.items():
            matches = sum(1 for v in sample if pat.match(v.strip()))
            ratio = matches / len(sample)
            if ratio >= 0.6:
                if cat == "credit_card":
                    luhn = sum(1 for v in sample if _luhn_ok(v)) / len(sample)
                    if luhn < 0.5:
                        continue
                value_hit, hit_ratio = cat, ratio
                break
    if name_hit and value_hit:
        return "likely", value_hit, min(0.99, 0.7 + 0.3 * hit_ratio)
    if value_hit:
        return "likely", value_hit, 0.6 + 0.3 * hit_ratio
    if name_hit:
        return "possible", name_hit, 0.5
    return "none", None, 0.9


def _entropy(counts: list[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts if c > 0)


def _column_profile(df: pl.DataFrame, col: str) -> dict[str, Any]:
    s = df.get_column(col)
    n = len(s)
    nulls = int(s.null_count())
    non_null = s.drop_nulls()
    distinct = int(non_null.n_unique()) if len(non_null) else 0
    prof: dict[str, Any] = {
        "name": col,
        "dtype": str(s.dtype),
        "count": n,
        "nulls": nulls,
        "null_ratio": round(nulls / n, 6) if n else 0.0,
        "distinct": distinct,
        "uniqueness": round(distinct / len(non_null), 6) if len(non_null) else 0.0,
    }
    if s.dtype.is_numeric() and len(non_null):
        mean_v: Any = non_null.mean()
        std_v: Any = non_null.std() or 0.0
        prof.update(
            min=_json_safe(non_null.min()),
            max=_json_safe(non_null.max()),
            mean=_json_safe(round(float(mean_v), 6)),
            std=_json_safe(round(float(std_v), 6)),
        )
    elif s.dtype in (pl.Date, pl.Datetime) and len(non_null):
        prof.update(min=str(non_null.min()), max=str(non_null.max()))

    if len(non_null):
        vc = non_null.cast(pl.String).value_counts(sort=True).head(TOP_VALUES_K)
        name_col = vc.columns[0]
        top = [
            {"value": row[name_col], "count": int(row["count"])} for row in vc.iter_rows(named=True)
        ]
        prof["top_values"] = top
        prof["entropy"] = round(_entropy([t["count"] for t in top]), 4)

    str_values = non_null.cast(pl.String).head(200).to_list() if len(non_null) else []
    level, category, conf = classify_pii(
        col, [str(v) for v in str_values], numeric=s.dtype.is_numeric()
    )
    prof["pii"] = {"level": level, "category": category, "confidence": conf}

    prof["pk_candidate"] = bool(
        nulls == 0 and n > 0 and prof["uniqueness"] >= PK_UNIQUENESS_THRESHOLD
    )
    return prof


def _json_safe(v: Any) -> Any:
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def profile_dataframe(
    df: pl.DataFrame, table_name: str, declared_schema: TableSchema | None = None
) -> dict[str, Any]:
    """Profile a sampled DataFrame. Pure function; no catalog access."""
    columns = [_column_profile(df, c) for c in df.columns]
    pk_candidates = [c["name"] for c in columns if c["pk_candidate"]]
    return {
        "table": table_name,
        "rows_sampled": len(df),
        "declared_row_count": declared_schema.row_count if declared_schema else None,
        "columns": columns,
        "pk_candidates": pk_candidates,
    }


def profile_source(
    cfg: ProjectConfig,
    catalog: Catalog,
    source_name: str,
    *,
    sample_rows: int = 10_000,
) -> list[dict[str, Any]]:
    """Profile every cataloged table of a source; persist profiles and
    confirm/annotate PK, PII, and FK candidates in the catalog."""
    from ai_data_platform.connectors import get_connector

    source = cfg.source(source_name)
    connector = get_connector(source)
    budget = SampleBudget(rows=sample_rows)

    samples: dict[str, pl.DataFrame] = {}
    summaries: list[dict[str, Any]] = []
    for tbl in connector.list_tables():
        df = connector.sample_data(tbl, budget)
        samples[tbl] = df
        prof = profile_dataframe(df, tbl, connector.get_table_schema(tbl))
        catalog.save_profile(tbl, prof)
        meta = catalog.get_table(tbl)
        if prof["pk_candidates"]:
            catalog.set_primary_key(meta["id"], prof["pk_candidates"][:1])
        for col in prof["columns"]:
            if col["pii"]["level"] != "none":
                catalog.set_pii(
                    meta["id"], col["name"], col["pii"]["level"], col["pii"]["category"]
                )
        summaries.append(
            {
                "table": tbl,
                "rows_sampled": prof["rows_sampled"],
                "pk_candidates": prof["pk_candidates"],
                "pii_columns": [c["name"] for c in prof["columns"] if c["pii"]["level"] != "none"],
            }
        )
        log.info("profiled %s (%d rows sampled)", tbl, prof["rows_sampled"])

    _confirm_fk_candidates(catalog, samples)
    return summaries


def _confirm_fk_candidates(catalog: Catalog, samples: dict[str, pl.DataFrame]) -> None:
    """Upgrade name-based FK candidates using inclusion dependency on samples."""
    for rel in catalog.get_relationships():
        child_df = samples.get(rel["child_table"])
        parent_df = samples.get(rel["parent_table"])
        if child_df is None or parent_df is None:
            continue
        cc, pc = rel["child_column"], rel["parent_column"]
        if cc not in child_df.columns or pc not in parent_df.columns:
            continue
        child_vals = child_df.get_column(cc).drop_nulls().cast(pl.String)
        parent_vals = set(parent_df.get_column(pc).drop_nulls().cast(pl.String).to_list())
        if len(child_vals) == 0 or not parent_vals:
            continue
        included = sum(1 for v in child_vals.to_list() if v in parent_vals)
        ratio = included / len(child_vals)
        if ratio >= FK_INCLUSION_THRESHOLD:
            catalog.add_relationship(
                rel["child_table"],
                cc,
                rel["parent_table"],
                pc,
                confidence=round(min(0.99, 0.7 + 0.29 * ratio), 3),
                provenance="inferred",
                evidence=f"inclusion {ratio:.1%} on samples",
            )
