"""Scan pipeline: connector -> catalog.

Discovers schemas/tables/columns, records name-based FK candidates
(structural pass; data-based confirmation happens in `adp profile`).
"""

from __future__ import annotations

import re
from typing import Any

from ai_data_platform.config import ProjectConfig
from ai_data_platform.connectors import get_connector
from ai_data_platform.connectors.base import TableSchema
from ai_data_platform.core.logging import get_logger
from ai_data_platform.metadata.catalog import Catalog, schema_fingerprint

log = get_logger("adp.scan")

_ID_SUFFIX = re.compile(r"(?i)^(?P<stem>.+?)_?(id|key|code)$")


def scan_source(cfg: ProjectConfig, catalog: Catalog, source_name: str) -> dict[str, Any]:
    """Scan one configured source into the catalog. Returns summary counts."""
    source = cfg.source(source_name)
    connector = get_connector(source)
    catalog.upsert_source(source.name, source.type)

    tables = connector.list_tables()
    schemas: list[TableSchema] = []
    for t in tables:
        schema = connector.get_table_schema(t)
        schemas.append(schema)
        catalog.upsert_table(source.name, schema)
        log.info("scanned table %s (%d columns)", t, len(schema.columns))

    fk_candidates = _name_based_fk_candidates(schemas)
    for child_t, child_c, parent_t, parent_c, conf, why in fk_candidates:
        catalog.add_relationship(
            child_t,
            child_c,
            parent_t,
            parent_c,
            confidence=conf,
            provenance="inferred",
            evidence=why,
        )

    catalog.mark_scanned(source.name, schema_fingerprint(schemas))
    return {
        "source": source.name,
        "tables": len(schemas),
        "columns": sum(len(s.columns) for s in schemas),
        "fk_candidates": len(fk_candidates),
    }


def scan_all(cfg: ProjectConfig, catalog: Catalog) -> list[dict[str, Any]]:
    return [scan_source(cfg, catalog, s.name) for s in cfg.sources]


_LAYER_PREFIX = re.compile(r"(?i)^(dim|fact|stg|raw|src|tbl)_")


def _base_name(name: str) -> str:
    """Strip dimensional-model layer prefixes: dim_customer -> customer."""
    return _LAYER_PREFIX.sub("", name.lower())


def _singular(name: str) -> str:
    n = _base_name(name)
    if n.endswith("ies"):
        return n[:-3] + "y"
    if n.endswith("ses"):
        return n[:-2]
    if n.endswith("s") and not n.endswith("ss"):
        return n[:-1]
    return n


def _name_based_fk_candidates(
    schemas: list[TableSchema],
) -> list[tuple[str, str, str, str, float, str]]:
    """`customer_id` in `orders` -> parent table `customers`.`customer_id`/`id`.

    Structural-only pass: confidence capped at 0.6 until data confirms inclusion.
    """
    by_name = {s.name.lower(): s for s in schemas}
    by_base = {_base_name(s.name): s for s in schemas}
    by_singular = {_singular(s.name): s for s in schemas}
    out: list[tuple[str, str, str, str, float, str]] = []
    for schema in schemas:
        for col in schema.columns:
            m = _ID_SUFFIX.match(col.name)
            if not m:
                continue
            stem = m.group("stem").lower()
            parent = (
                by_name.get(stem)
                or by_name.get(stem + "s")
                or by_base.get(stem)
                or by_base.get(stem + "s")
                or by_singular.get(stem)
            )
            if parent is None or parent.name == schema.name:
                continue
            parent_cols = {c.name.lower(): c.name for c in parent.columns}
            target = parent_cols.get(col.name.lower()) or parent_cols.get("id")
            if target is None:
                continue
            out.append(
                (
                    schema.name,
                    col.name,
                    parent.name,
                    target,
                    0.6,
                    f"name match: {col.name} -> {parent.name}.{target}",
                )
            )
    return out
