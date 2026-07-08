"""Semantic model builder.

Internal model is the source of truth; formats (generic YAML, Cube YAML) are
renderers over it. Detection is heuristic + confidence-tagged; deterministic
(no LLM in the naming path).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from ai_data_platform.core.exceptions import SemanticModelError

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.metadata.catalog import Catalog

MEASURE_NAME_HINTS = (
    "amount",
    "price",
    "total",
    "cost",
    "revenue",
    "salary",
    "balance",
    "fee",
    "qty",
    "quantity",
    "units",
    "score",
    "duration",
    "value",
)


def _classify_table(meta: dict[str, Any], fk_out: int, fk_in: int) -> tuple[str, float]:
    """fact vs dimension with confidence."""
    numeric_measures = sum(
        1
        for c in meta["columns"]
        if c["type"] in ("int", "float")
        and not c["primary_key"]
        and any(h in c["name"].lower() for h in MEASURE_NAME_HINTS)
    )
    has_time = any(c["type"] in ("date", "datetime") for c in meta["columns"])
    fact_score = 0.2 * min(fk_out, 3) + 0.3 * min(numeric_measures, 3) + (0.2 if has_time else 0)
    dim_score = 0.25 * min(fk_in, 3) + (0.2 if fk_out == 0 else 0)
    if fact_score >= dim_score and fact_score > 0.3:
        return "fact", round(min(0.95, 0.5 + fact_score / 2), 2)
    if dim_score > 0.2:
        return "dimension", round(min(0.95, 0.5 + dim_score / 2), 2)
    return "dimension", 0.5


def _agg_for(col: dict[str, Any]) -> str:
    n = col["name"].lower()
    if any(h in n for h in ("qty", "quantity", "units", "count")):
        return "sum"
    if any(h in n for h in ("price", "rate", "score", "duration")):
        return "avg"
    if col["primary_key"] or n.endswith("_id"):
        return "count_distinct"
    return "sum"


def build_semantic_model(catalog: Catalog, name: str = "default") -> dict[str, Any]:
    """Build the internal semantic model from the catalog."""
    tables = catalog.list_tables()
    if not tables:
        raise SemanticModelError(
            "Catalog is empty.", hint="Run `adp scan` (and ideally `adp profile`) first."
        )
    rels = [r for r in catalog.get_relationships() if r["confidence"] >= 0.6]
    fk_out: dict[str, int] = {}
    fk_in: dict[str, int] = {}
    for r in rels:
        fk_out[r["child_table"]] = fk_out.get(r["child_table"], 0) + 1
        fk_in[r["parent_table"]] = fk_in.get(r["parent_table"], 0) + 1

    entities: list[dict[str, Any]] = []
    for t in tables:
        meta = catalog.get_table(t["table"])
        kind, confidence = _classify_table(
            meta, fk_out.get(t["table"], 0), fk_in.get(t["table"], 0)
        )
        catalog.set_table_kind(meta["id"], kind)
        pk = next((c["name"] for c in meta["columns"] if c["primary_key"]), None)
        fk_cols = {r["child_column"] for r in rels if r["child_table"] == t["table"]}

        dimensions, time_dimensions, measures = [], [], []
        for c in meta["columns"]:
            n = c["name"]
            if c["type"] in ("date", "datetime"):
                time_dimensions.append(
                    {
                        "name": n,
                        "column": n,
                        "granularities": ["day", "week", "month", "quarter", "year"],
                    }
                )
            elif (
                kind == "fact"
                and c["type"] in ("int", "float")
                and not c["primary_key"]
                and n not in fk_cols
                and any(h in n.lower() for h in MEASURE_NAME_HINTS)
            ):
                measures.append({"name": f"{n}_{_agg_for(c)}", "column": n, "agg": _agg_for(c)})
            elif not c["primary_key"]:
                dimensions.append(
                    {
                        "name": n,
                        "column": n,
                        "type": "boolean" if c["type"] == "bool" else "categorical",
                    }
                )
        if kind == "fact":
            measures.insert(0, {"name": "count", "column": pk or "*", "agg": "count"})

        entities.append(
            {
                "name": t["table"],
                "kind": kind,
                "confidence": confidence,
                "primary_key": pk,
                "dimensions": dimensions,
                "time_dimensions": time_dimensions,
                "measures": measures,
            }
        )

    joins = [
        {
            "left": r["child_table"],
            "right": r["parent_table"],
            "relationship": "many_to_one",
            "sql_on": f"{r['child_table']}.{r['child_column']} = "
            f"{r['parent_table']}.{r['parent_column']}",
            "confidence": r["confidence"],
        }
        for r in rels
    ]
    model = {"version": 1, "name": name, "entities": entities, "joins": joins}
    catalog.save_semantic_model(name, model)
    return model


def render_semantic_model(model: dict[str, Any], fmt: str = "generic") -> str:
    if fmt == "generic":
        return yaml.safe_dump(model, sort_keys=False)
    if fmt == "cube":
        return _render_cube(model)
    raise SemanticModelError(f"Unknown semantic format {fmt!r}.", hint="Supported: generic, cube.")


def _render_cube(model: dict[str, Any]) -> str:
    """Cube.js model YAML (`cubes:`) per semantic-layer-engineer skill."""
    joins_by_table: dict[str, list[dict[str, Any]]] = {}
    for j in model["joins"]:
        joins_by_table.setdefault(j["left"], []).append(j)

    cubes = []
    for e in model["entities"]:
        dimensions: dict[str, Any] = {}
        if e["primary_key"]:
            dimensions[e["primary_key"]] = {
                "sql": e["primary_key"],
                "type": "number",
                "primary_key": True,
            }
        for d in e["dimensions"]:
            dimensions[d["name"]] = {
                "sql": d["column"],
                "type": "boolean" if d["type"] == "boolean" else "string",
            }
        for td in e["time_dimensions"]:
            dimensions[td["name"]] = {"sql": td["column"], "type": "time"}

        measures: dict[str, Any] = {}
        for m in e["measures"]:
            agg = {"count_distinct": "count_distinct_approx"}.get(m["agg"], m["agg"])
            entry: dict[str, Any] = {"type": "count" if m["agg"] == "count" else agg}
            if m["agg"] != "count":
                entry["sql"] = m["column"]
            measures[m["name"]] = entry

        joins = {
            j["right"]: {
                "sql": "{CUBE}."
                + j["sql_on"].split(" = ")[0].split(".", 1)[1]
                + " = {"
                + j["right"]
                + "}."
                + j["sql_on"].split(" = ")[1].split(".", 1)[1],
                "relationship": j["relationship"],
            }
            for j in joins_by_table.get(e["name"], [])
        }

        cube: dict[str, Any] = {
            "name": e["name"],
            "sql_table": e["name"],
            "dimensions": dimensions,
            "measures": measures,
        }
        if joins:
            cube["joins"] = joins
        cubes.append(cube)
    return yaml.safe_dump({"cubes": cubes}, sort_keys=False)
