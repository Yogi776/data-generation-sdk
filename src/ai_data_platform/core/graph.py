"""Shared graph utilities for FK-safe ordering (generation + load)."""

from __future__ import annotations

from ai_data_platform.core.logging import get_logger

log = get_logger("adp.graph")


def topo_sort(tables: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Parents-first order; cycles broken by dropping back-edges (logged).

    ``edges`` are ``(child, parent)`` pairs.
    """
    deps: dict[str, set[str]] = {t: set() for t in tables}
    for child, parent in edges:
        if child in deps and parent in deps and child != parent:
            deps[child].add(parent)
    ordered: list[str] = []
    remaining = dict(deps)
    while remaining:
        ready = sorted(t for t, d in remaining.items() if not d)
        if not ready:
            victim = sorted(remaining)[0]
            log.warning("relationship cycle detected; breaking at %s", victim)
            remaining[victim] = set()
            continue
        for t in ready:
            ordered.append(t)
            del remaining[t]
            for d in remaining.values():
                d.discard(t)
    return ordered


def topo_waves(tables: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Group tables into FK-safe waves (tables in a wave may run in parallel)."""
    if not tables:
        return []
    deps: dict[str, set[str]] = {t: set() for t in tables}
    for child, parent in edges:
        if child in deps and parent in deps and child != parent:
            deps[child].add(parent)
    waves: list[list[str]] = []
    remaining = {t: set(deps[t]) for t in tables}
    while remaining:
        ready = sorted(t for t, d in remaining.items() if not d)
        if not ready:
            victim = sorted(remaining)[0]
            log.warning("relationship cycle detected in topo_waves; breaking at %s", victim)
            remaining[victim] = set()
            continue
        waves.append(ready)
        for t in ready:
            del remaining[t]
            for d in remaining.values():
                d.discard(t)
    return waves
