"""Shared graph utilities for FK-safe ordering (generation + load)."""

from __future__ import annotations

from ai_data_platform.core.logging import get_logger

log = get_logger("adp.graph")


def _build_adjacency(
    tables: list[str],
    edges: list[tuple[str, str]],
) -> tuple[dict[str, int], dict[str, set[str]]]:
    """Build in-degree and parent->children adjacency. ``edges`` are ``(child, parent)``."""
    in_degree = {t: 0 for t in tables}
    children: dict[str, set[str]] = {t: set() for t in tables}
    seen: set[tuple[str, str]] = set()
    for child, parent in edges:
        if child in in_degree and parent in in_degree and child != parent:
            if (child, parent) not in seen:
                seen.add((child, parent))
                in_degree[child] += 1
                children[parent].add(child)
    return in_degree, children


def _break_cycle(in_degree: dict[str, int]) -> str:
    """Pick a deterministic victim and break the cycle by zeroing its in-degree."""
    victim = sorted(t for t, d in in_degree.items() if d > 0)[0]
    log.warning("relationship cycle detected; breaking at %s", victim)
    in_degree[victim] = 0
    return victim


def topo_sort(tables: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Parents-first order; cycles broken by dropping back-edges (logged).

    ``edges`` are ``(child, parent)`` pairs. O(V + E) via Kahn's algorithm.
    """
    if not tables:
        return []
    in_degree, children = _build_adjacency(tables, edges)
    ordered: list[str] = []
    remaining = set(tables)

    while remaining:
        ready = sorted(t for t in remaining if in_degree[t] == 0)
        if not ready:
            _break_cycle(in_degree)
            continue
        for node in ready:
            ordered.append(node)
            remaining.discard(node)
            for child in children[node]:
                if child in remaining:
                    in_degree[child] -= 1
    return ordered


def topo_waves(tables: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Group tables into FK-safe waves (tables in a wave may run in parallel).

    O(V + E) via Kahn's algorithm.
    """
    if not tables:
        return []
    in_degree, children = _build_adjacency(tables, edges)
    waves: list[list[str]] = []
    remaining = set(tables)

    while remaining:
        ready = sorted(t for t in remaining if in_degree[t] == 0)
        if not ready:
            _break_cycle(in_degree)
            continue
        waves.append(ready)
        for node in ready:
            remaining.discard(node)
            for child in children[node]:
                if child in remaining:
                    in_degree[child] -= 1
    return waves
