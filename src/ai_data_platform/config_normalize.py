"""Normalize simplified pipeline-style adp.yaml into canonical ProjectConfig dict.

Supports:
  - Legacy ``destinations`` / ``load`` blocks (passthrough)
  - ``pipeline`` / ``pipelines`` with ``source.address`` + ``sink.address``
  - ``workflow.dag[].spec.stackSpec`` (DataOS-style, k8s fields ignored)
"""

from __future__ import annotations

import re
from typing import Any

_KEBAB_RE = re.compile(r"-([a-z])")
_CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")


def _to_snake(key: str) -> str:
    k = _KEBAB_RE.sub(lambda m: m.group(1).upper(), str(key))
    k = _CAMEL_RE.sub(r"\1_\2", k)
    return k.lower()


def _normalize_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {_to_snake(str(k)): _normalize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_keys(v) for v in obj]
    return obj


def _merge_options(block: dict[str, Any]) -> dict[str, Any]:
    """Flatten ``options`` into the endpoint dict (kebab → snake)."""
    out = _normalize_keys(dict(block))
    opts = out.pop("options", None)
    if isinstance(opts, dict):
        out = {**out, **_normalize_keys(opts)}
    return out


def _endpoint_address(block: dict[str, Any]) -> str | None:
    b = _merge_options(block)
    return b.get("address") or b.get("uri")


def _pipeline_from_endpoints(
    name: str,
    source: dict[str, Any] | None,
    sink: dict[str, Any],
) -> dict[str, Any]:
    sink_b = _merge_options(sink)
    address = sink_b.pop("address", None) or sink_b.pop("uri", None)
    if not address:
        raise ValueError(f"pipeline {name!r}: sink.address is required")

    dest: dict[str, Any] = {
        "name": name,
        "uri": address,
    }

    # sink → destination fields
    if table := sink_b.pop("dest_table", None) or sink_b.pop("table", None):
        if "." in str(table) and "table_prefix" not in sink_b:
            dest["tables"] = {_table_key_from_dest(str(table)): str(table)}
        else:
            dest["table_prefix"] = str(table)
    if "table_prefix" in sink_b:
        dest["table_prefix"] = sink_b.pop("table_prefix")
    for key in (
        "incremental_strategy",
        "primary_key",
        "incremental_key",
        "ingestr_options",
        "table_ingestr_options",
        "auto_extract_partition",
        "stream",
        "tables",
    ):
        if key in sink_b:
            dest[key] = sink_b.pop(key)

    # Remaining sink keys → ingestr_options
    if sink_b:
        dest.setdefault("ingestr_options", {}).update(sink_b)

    if source:
        src_b = _merge_options(source)
        src_uri = src_b.pop("address", None) or src_b.pop("uri", None)
        if not src_uri:
            raise ValueError(f"pipeline {name!r}: source.address is required when source is set")
        live_source: dict[str, Any] = {"uri": src_uri}
        if tbl := src_b.pop("table", None) or src_b.pop("source_table", None):
            live_source["table"] = tbl
        for key in ("sql", "incremental_key", "ingestr_options"):
            if key in src_b:
                live_source[key] = src_b.pop(key)
        if src_b:
            live_source.setdefault("ingestr_options", {}).update(src_b)
        dest["source"] = live_source

    return dest


def _table_key_from_dest(dest_table: str) -> str:
    """PUBLIC.fact_order → fact_order (catalog/spec table name)."""
    return dest_table.rsplit(".", 1)[-1]


def _collect_pipelines(raw: dict[str, Any]) -> list[tuple[str, dict[str, Any] | None, dict[str, Any]]]:
    items: list[tuple[str, dict[str, Any] | None, dict[str, Any]]] = []

    if "pipeline" in raw:
        p = raw["pipeline"]
        if not isinstance(p, dict):
            raise ValueError("pipeline must be a mapping")
        name = str(p.get("name") or "default")
        source = p.get("source")
        sink = p.get("sink")
        if not isinstance(sink, dict):
            raise ValueError("pipeline.sink is required")
        items.append((name, source if isinstance(source, dict) else None, sink))

    for i, p in enumerate(raw.get("pipelines") or []):
        if not isinstance(p, dict):
            raise ValueError(f"pipelines[{i}] must be a mapping")
        name = str(p.get("name") or f"pipeline_{i + 1}")
        source = p.get("source")
        sink = p.get("sink")
        if not isinstance(sink, dict):
            raise ValueError(f"pipelines[{i}].sink is required")
        items.append((name, source if isinstance(source, dict) else None, sink))

    wf = raw.get("workflow")
    if isinstance(wf, dict):
        for i, node in enumerate(wf.get("dag") or []):
            if not isinstance(node, dict):
                continue
            name = str(node.get("name") or f"step_{i + 1}")
            spec = node.get("spec") or {}
            stack_spec = spec.get("stackSpec") or spec.get("stack_spec") or {}
            source = stack_spec.get("source")
            sink = stack_spec.get("sink")
            if isinstance(sink, dict):
                items.append(
                    (
                        name,
                        source if isinstance(source, dict) else None,
                        sink,
                    )
                )

    return items


def _merge_destinations(destinations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Combine pipelines that share the same sink+source URIs into one destination."""
    if len(destinations) <= 1:
        return destinations

    grouped: dict[tuple[str, str | None], dict[str, Any]] = {}
    order: list[tuple[str, str | None]] = []

    for dest in destinations:
        src_uri = (dest.get("source") or {}).get("uri")
        key = (dest["uri"], src_uri)
        if key not in grouped:
            grouped[key] = dest
            order.append(key)
            continue
        existing = grouped[key]
        existing.setdefault("tables", {}).update(dest.get("tables") or {})
        for opt_key in ("ingestr_options", "table_ingestr_options"):
            if dest.get(opt_key):
                existing.setdefault(opt_key, {}).update(dest[opt_key])

    return [grouped[k] for k in order]


def normalize_adp_yaml(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a dict suitable for ``ProjectConfig.model_validate``."""
    if not raw:
        return raw

    out = dict(raw)

    # name → project (simple format uses ``name``)
    if "project" not in out and "name" in out:
        out["project"] = out["name"]

    # version: v1 → 1
    ver = out.get("version")
    if isinstance(ver, str) and ver.lower().startswith("v"):
        try:
            out["version"] = int(ver[1:])
        except ValueError:
            pass

    pipelines = _collect_pipelines(out)
    if not pipelines:
        return out

    destinations = [_pipeline_from_endpoints(name, src, sink) for name, src, sink in pipelines]
    destinations = _merge_destinations(destinations)

    out["destinations"] = destinations

    # Default load target
    load = dict(out.get("load") or {})
    pipeline_load = (out.get("pipeline") or {}).get("load") if isinstance(out.get("pipeline"), dict) else None
    if isinstance(pipeline_load, dict):
        load = {**pipeline_load, **load}
    if not load.get("default_destination") and destinations:
        load["default_destination"] = destinations[0]["name"]
    if destinations and destinations[0].get("source"):
        load.setdefault("require_quality_pass", False)
    out["load"] = load

    # Strip pipeline-only keys before pydantic validation
    for key in ("pipeline", "pipelines", "workflow", "name"):
        out.pop(key, None)

    return out
