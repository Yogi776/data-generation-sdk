"""Declarative dataset specs: define tables/columns/distributions in YAML,
generate without any seed data.

This closes the cold-start gap: instead of providing sample rows for the
profiler to learn from, you declare what the data should look like and
`apply_spec` writes the same catalog entries + profile payloads that
scan+profile would have produced. The existing plan compiler and generator
then work unchanged.

Example spec.yaml:

    version: 1
    tables:
      - name: dim_customer
        columns:
          - {name: customer_id, type: uuid, primary_key: true}
          - {name: gender, type: string, values: {Male: 48, Female: 50, Other: 2}}
          - {name: age, type: int, min: 18, max: 75}
          - {name: annual_income, type: float, mean: 850000, std: 500000, min: 0}
          - {name: signup_date, type: date, start: 2020-01-01, end: 2026-06-01}
          - {name: coupon_code, type: string, null_ratio: 0.65}
      - name: fact_transaction
        columns:
          - {name: transaction_id, type: uuid, primary_key: true}
          - {name: customer_id, type: uuid, references: dim_customer.customer_id}
          - {name: payment_method, type: string,
             values: {UPI: 40, Credit Card: 22, Debit Card: 15, Wallet: 10, COD: 8, PayPal: 5}}

`values` maps category -> weight (any positive numbers; normalized).
`references` declares a foreign key (parent generated first, zero orphans).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_data_platform.connectors.base import ColumnSchema, TableSchema
from ai_data_platform.core.exceptions import ConfigError

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.metadata.catalog import Catalog

SPEC_VERSION = 1

ColumnType = Literal["int", "float", "string", "bool", "date", "datetime", "uuid"]


class AfterSpec(BaseModel):
    """Temporal dependency: this column = other column + random offset."""

    model_config = ConfigDict(extra="forbid")

    column: str
    min_minutes: int = 1
    max_minutes: int = 1440


class ValuesBySpec(BaseModel):
    """Hierarchical categorical dependency: value distribution conditioned on
    another column (country -> state -> city consistency).

        values_by:
          column: state
          mapping:
            Maharashtra: {Mumbai: 55, Pune: 35, Nagpur: 10}
            Karnataka: {Bangalore: 80, Mysore: 20}
    """

    model_config = ConfigDict(extra="forbid")

    column: str
    mapping: dict[str, dict[str, float]]


class ColumnSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: ColumnType = "string"
    primary_key: bool = False
    references: str | None = None  # "parent_table.parent_column"
    values: dict[str, float] | list[str] | None = None  # categorical (weights optional)
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    start: date | None = None  # date/datetime range
    end: date | None = None
    null_ratio: float = Field(default=0.0, ge=0.0, le=0.95)
    format: str | None = None  # string template: '#'=digit '?'=letter, e.g. "ORD-2025-######"
    # -- cross-column dependencies (applied in declared column order) --------
    expr: str | None = None  # e.g. "unit_price * quantity - discount_amount"
    after: AfterSpec | None = None  # e.g. payment_date after order_date
    null_unless: str | None = None  # e.g. "order_status = 'Returned'"
    values_by: ValuesBySpec | None = None  # hierarchical: city depends on state

    @field_validator("references")
    @classmethod
    def _ref_shape(cls, v: str | None) -> str | None:
        if v is not None and v.count(".") != 1:
            raise ValueError('references must be "table.column"')
        return v


Relationship = Literal["one_to_many", "many_to_one", "one_to_one"]


class TableJoinSpec(BaseModel):
    """Cube.js-style join declared inside a table.

        joins:
          - name: battery
            relationship: one_to_many
            sql: "{TABLE.device_id} = {battery.device_id}"

    `{TABLE}` (or `{CUBE}`) refers to the enclosing table. Relationship reads
    current-table -> named table: one_to_many means one current row has many
    rows in `name` (the named table holds the FK); many_to_one means the
    current table holds the FK; one_to_one gives the named table exactly one
    row per current row (unique FK permutation).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    relationship: Relationship = "many_to_one"
    sql: str


class TableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    columns: list[ColumnSpec]
    joins: list[TableJoinSpec] = Field(default_factory=list)
    rows: int | None = Field(default=None, ge=1)  # default row count for this table

    @field_validator("columns")
    @classmethod
    def _has_columns(cls, v: list[ColumnSpec]) -> list[ColumnSpec]:
        if not v:
            raise ValueError("table needs at least one column")
        return v


class JoinSpec(BaseModel):
    """Explicit join declaration (alternative to column-level `references`).

    Cardinality semantics:
    - one_to_many:  left is the parent (the "one"), right holds the FK (the "many").
    - many_to_one:  left holds the FK (the "many"), right is the parent (the "one").
    - one_to_one:   left holds the FK; every generated FK value is unique
                    (a permutation of parent keys — requires rows <= parent rows).
    """

    model_config = ConfigDict(extra="forbid")

    left: str  # "table.column"
    right: str  # "table.column"
    relationship: Relationship = "many_to_one"

    @field_validator("left", "right")
    @classmethod
    def _side_shape(cls, v: str) -> str:
        if v.count(".") != 1:
            raise ValueError('join sides must be "table.column"')
        return v

    def normalized(self) -> tuple[str, str, str, str, str]:
        """Return (child_table, child_column, parent_table, parent_column, kind)."""
        lt, lc = self.left.split(".", 1)
        rt, rc = self.right.split(".", 1)
        if self.relationship == "one_to_many":
            return rt, rc, lt, lc, "many_to_one"
        if self.relationship == "one_to_one":
            return lt, lc, rt, rc, "one_to_one"
        return lt, lc, rt, rc, "many_to_one"


class DatasetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = SPEC_VERSION
    tables: list[TableSpec]
    joins: list[JoinSpec] = Field(default_factory=list)


# {table.column} or {table}.column — both Cube-style reference forms
_JOIN_REF = re.compile(r"\{([A-Za-z_]\w*)(?:\.(\w+))?\}(?:\.(\w+))?")


def _parse_join_sql(sql: str, current: str, target: str) -> tuple[str, str]:
    """Extract (current_column, target_column) from a join sql expression."""
    refs: list[tuple[str, str]] = []
    for m in _JOIN_REF.finditer(sql):
        tbl, col = m.group(1), m.group(2) or m.group(3)
        if not col:
            raise ConfigError(
                f"Join sql {sql!r}: reference {{{tbl}}} has no column.",
                hint='Use "{TABLE.col} = {other_table.col}".',
            )
        if tbl.upper() in ("TABLE", "CUBE"):
            tbl = current
        refs.append((tbl, col))
    if len(refs) != 2:
        raise ConfigError(
            f"Join sql {sql!r} must reference exactly two columns.",
            hint='Example: "{TABLE.device_id} = {battery.device_id}"',
        )
    by_table = dict(refs)
    if current not in by_table or target not in by_table:
        raise ConfigError(
            f"Join sql {sql!r} must reference {current!r} (or TABLE) and {target!r}.",
        )
    return by_table[current], by_table[target]


def load_spec_text(text: str) -> DatasetSpec:
    """Validate spec YAML content (used by AI-proposed specs and MCP)."""
    try:
        raw = yaml.safe_load(text) or {}
        return DatasetSpec.model_validate(raw)
    except yaml.YAMLError as e:
        raise ConfigError(f"Spec is not valid YAML: {e}") from e
    except ValueError as e:
        raise ConfigError(f"Spec failed validation: {e}") from e


_PROPOSE_SYSTEM = """You are a synthetic-data architect. Design a dataset spec as YAML.
Output ONLY YAML (no prose, no code fences). Schema:

version: 1
tables:
  - name: <snake_case>
    joins:                                   # optional, Cube.js style
      - name: <other_table>
        relationship: one_to_many | many_to_one | one_to_one
        sql: "{TABLE.col} = {other_table.col}"
    columns:
      - name: <snake_case>
        type: int | float | string | bool | date | datetime | uuid
        primary_key: true                    # exactly one per table
        values: {CategoryA: 60, CategoryB: 40}   # weighted categories (use REAL-WORLD proportions)
        mean: <num>  std: <num>  min: <num>  max: <num>   # numeric shape
        start: 2024-01-01  end: 2026-01-01   # date/datetime range
        format: "ORD-######"                 # '#'=digit '?'=letter
        null_ratio: 0.3                      # optional sparsity
        expr: "price * qty - discount"       # arithmetic from sibling columns
        after: {column: order_date, min_minutes: 1, max_minutes: 120}  # temporal order
        null_unless: "status = 'Returned'"   # conditional presence
        values_by:                           # hierarchy (city within state)
          column: state
          mapping: {StateA: {City1: 60, City2: 40}}

Rules:
- Every table has exactly one primary_key column (type uuid, or int for sequences).
- FK columns are declared via joins; the FK column must exist in the child table.
- Columns used in expr/after must be declared BEFORE the column referencing them.
- REALISM: the engine has built-in realistic samplers triggered by column NAME —
  full_name/first_name/last_name (real human names), email (name-based real
  addresses), phone/mobile, address/street, city, country. For these columns give
  ONLY name+type — NEVER a format template (format on them produces gibberish).
- Use format ONLY for codes/IDs with fixed shapes (order_number "ORD-######",
  tracking "TRK-##########", MRN "MRN-#######").
- Money/amount/price/total columns: give mean+std (engine fits lognormal).
  Count/quantity columns: mean+min (engine fits Poisson).
- Use realistic industry-accurate category weights and numeric ranges; ground
  them in the research notes when provided.

REALISTIC VALUES — important:
- For person/contact fields, name the column well and add NOTHING else:
  full_name, first_name, last_name, email, phone_number, address_line1, city —
  the engine has built-in realistic samplers keyed on these names.
  NEVER use `format` for emails or names (it produces gibberish).
- Use `format` ONLY for business codes/IDs: "ORD-######", "MRN-#######", "??-####".
- Money/amount/price columns: give mean+std (engine fits a lognormal);
  quantity/count columns: give mean (engine fits a Poisson).
- Primary keys: type uuid for entity IDs, or type int (sequential), or a string
  with `format` for business-style keys — uniqueness is guaranteed by the engine."""


def propose_spec(
    provider_cfg: Any, description: str, research_notes: str = ""
) -> tuple[str, DatasetSpec]:
    """Ask the configured LLM to draft a spec; validate strictly, retry once
    with the validation error, then fail typed. Returns (yaml_text, spec)."""
    from ai_data_platform.core.exceptions import AIExtractionError
    from ai_data_platform.sql.providers import get_provider

    provider = get_provider(provider_cfg)
    user = f"Design a dataset spec for: {description}"
    if research_notes:
        user += f"\n\nResearch notes (ground distributions in these):\n{research_notes}"

    def _strip(raw: str) -> str:
        t = raw.strip()
        if t.startswith("```"):
            t = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", t).strip()
        return t

    yaml_text = _strip(provider.complete(_PROPOSE_SYSTEM, user))
    try:
        return yaml_text, load_spec_text(yaml_text)
    except ConfigError as first_error:
        retry = provider.complete(
            _PROPOSE_SYSTEM,
            f"{user}\n\nYour previous YAML failed validation with:\n{first_error}\n"
            "Fix it and output only the corrected YAML.",
        )
        yaml_text = _strip(retry)
        try:
            return yaml_text, load_spec_text(yaml_text)
        except ConfigError as e:
            raise AIExtractionError(
                f"Model could not produce a valid spec after retry: {e}",
                hint="Try a more specific description, or draft the spec manually.",
            ) from e


def load_spec(path: str | Path) -> DatasetSpec:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Spec file {p} does not exist.")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return DatasetSpec.model_validate(raw)
    except yaml.YAMLError as e:
        raise ConfigError(f"Spec is not valid YAML: {e}") from e
    except ValueError as e:
        raise ConfigError(f"Spec failed validation: {e}") from e


def _catalog_type(t: ColumnType) -> str:
    return "string" if t == "uuid" else t


def _column_profile(col: ColumnSpec) -> dict[str, Any]:
    """Synthesize the profile payload the profiler would have produced."""
    prof: dict[str, Any] = {
        "name": col.name,
        "dtype": col.type,
        "count": 1000,
        "nulls": int(col.null_ratio * 1000),
        "null_ratio": col.null_ratio,
        "distinct": 1000 if col.primary_key else 100,
        "uniqueness": 1.0 if col.primary_key else 0.1,
        "pk_candidate": col.primary_key,
        "pii": {"level": "none", "category": None, "confidence": 0.9},
    }
    if col.values is not None:
        pairs = (
            list(col.values.items())
            if isinstance(col.values, dict)
            else [(v, 1.0) for v in col.values]
        )
        total = sum(w for _, w in pairs) or 1.0
        prof["top_values"] = [
            {"value": str(v), "count": max(1, round(w / total * 1000))} for v, w in pairs
        ]
        prof["distinct"] = len(pairs)
        prof["uniqueness"] = len(pairs) / 1000
    if col.mean is not None:
        prof["mean"] = col.mean
        prof["std"] = col.std if col.std is not None else abs(col.mean) * 0.3
    if col.min is not None:
        prof["min"] = col.min
    if col.max is not None:
        prof["max"] = col.max
    if col.start is not None:
        prof["min"] = col.start.isoformat()
    if col.end is not None:
        prof["max"] = col.end.isoformat()
    if col.format:
        prof["format"] = col.format
    derive: dict[str, Any] = {}
    if col.expr:
        derive["expr"] = col.expr
    if col.after:
        derive["after"] = col.after.model_dump()
    if col.null_unless:
        derive["null_unless"] = col.null_unless
    if col.values_by:
        derive["conditional"] = col.values_by.model_dump()
    if derive:
        prof["derive"] = derive
    return prof


def apply_spec(catalog: Catalog, spec: DatasetSpec, source_name: str = "spec") -> dict[str, Any]:
    """Write spec-declared tables, keys, relationships, and profiles to the catalog.

    After this, `build_plan`/`generate` work exactly as if the tables had been
    scanned and profiled from a real source.
    """
    table_names = {t.name for t in spec.tables}
    catalog.upsert_source(source_name, "spec")

    for table in spec.tables:
        schema = TableSchema(
            name=table.name,
            schema_name="spec",
            columns=tuple(
                ColumnSchema(
                    name=c.name,
                    data_type=_catalog_type(c.type),
                    nullable=c.null_ratio > 0,
                    ordinal=i,
                )
                for i, c in enumerate(table.columns)
            ),
        )
        table_id = catalog.upsert_table(source_name, schema)
        pks = [c.name for c in table.columns if c.primary_key]
        if pks:
            catalog.set_primary_key(table_id, pks[:1])
        catalog.save_profile(
            table.name,
            {
                "table": table.name,
                "rows_sampled": 1000,
                "declared_row_count": None,
                "spec_rows": table.rows,  # per-table default row count
                "source": "spec",
                "columns": [_column_profile(c) for c in table.columns],
                "pk_candidates": pks[:1],
            },
        )

    columns_by_table = {t.name: {c.name for c in t.columns} for t in spec.tables}

    def _add_fk(
        child_t: str, child_c: str, parent_t: str, parent_c: str, kind: str, evidence: str
    ) -> None:
        for t, c in ((child_t, child_c), (parent_t, parent_c)):
            if t not in table_names:
                raise ConfigError(
                    f"Join references unknown table {t!r}.",
                    hint=f"Declared tables: {', '.join(sorted(table_names))}",
                )
            if c not in columns_by_table[t]:
                raise ConfigError(
                    f"Join references unknown column {t}.{c}.",
                    hint=f"Columns of {t}: {', '.join(sorted(columns_by_table[t]))}",
                )
        catalog.add_relationship(
            child_t,
            child_c,
            parent_t,
            parent_c,
            kind=kind,
            confidence=1.0,
            provenance="user_stated",
            evidence=evidence,
        )

    fk_count = 0
    for table in spec.tables:
        for col in table.columns:
            if not col.references:
                continue
            parent_table, parent_col = col.references.split(".", 1)
            _add_fk(
                table.name,
                col.name,
                parent_table,
                parent_col,
                "many_to_one",
                "column references in spec",
            )
            fk_count += 1

    # Cube.js-style joins nested under tables
    for table in spec.tables:
        for tj in table.joins:
            cur_col, tgt_col = _parse_join_sql(tj.sql, table.name, tj.name)
            if tj.relationship == "many_to_one":
                child_t, child_c = table.name, cur_col
                parent_t, parent_c = tj.name, tgt_col
                kind = "many_to_one"
            else:  # one_to_many / one_to_one: the named table holds the FK
                child_t, child_c = tj.name, tgt_col
                parent_t, parent_c = table.name, cur_col
                kind = "one_to_one" if tj.relationship == "one_to_one" else "many_to_one"
            _add_fk(
                child_t,
                child_c,
                parent_t,
                parent_c,
                kind,
                f"table join in spec ({tj.relationship})",
            )
            fk_count += 1

    for join in spec.joins:
        child_t, child_c, parent_t, parent_c, kind = join.normalized()
        _add_fk(
            child_t,
            child_c,
            parent_t,
            parent_c,
            kind,
            f"joins section in spec ({join.relationship})",
        )
        fk_count += 1

    return {
        "source": source_name,
        "tables": len(spec.tables),
        "columns": sum(len(t.columns) for t in spec.tables),
        "relationships": fk_count,
    }
