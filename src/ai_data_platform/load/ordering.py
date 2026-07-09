"""FK-safe table ordering for load waves."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_data_platform.core.graph import topo_waves

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.metadata.catalog import Catalog


def table_waves(
    catalog: Catalog,
    tables: list[str] | None = None,
    *,
    fk_confidence_min: float = 0.5,
) -> list[list[str]]:
    """Return FK-safe waves of table names (parallel within a wave)."""
    all_tables = [t["table"] for t in catalog.list_tables()]
    selected = tables or all_tables
    rels = [
        r
        for r in catalog.get_relationships()
        if r["confidence"] >= fk_confidence_min
        and r["child_table"] in selected
        and r["parent_table"] in selected
    ]
    edges = [(r["child_table"], r["parent_table"]) for r in rels]
    return topo_waves(selected, edges)
