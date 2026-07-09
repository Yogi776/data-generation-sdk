"""Tests for core/graph topo_sort and topo_waves."""

from __future__ import annotations

from ai_data_platform.core.graph import topo_sort, topo_waves


def test_topo_sort_parents_first() -> None:
    order = topo_sort(
        ["fact_order_item", "dim_customer", "fact_order", "dim_product"],
        [("fact_order", "dim_customer"), ("fact_order_item", "fact_order")],
    )
    assert order.index("dim_customer") < order.index("fact_order")
    assert order.index("fact_order") < order.index("fact_order_item")


def test_topo_waves_parallel_dims() -> None:
    waves = topo_waves(
        ["dim_customer", "dim_product", "fact_order", "fact_order_item"],
        [
            ("fact_order", "dim_customer"),
            ("fact_order", "dim_product"),
            ("fact_order_item", "fact_order"),
        ],
    )
    assert len(waves) == 3
    assert set(waves[0]) == {"dim_customer", "dim_product"}
    assert waves[1] == ["fact_order"]
    assert waves[2] == ["fact_order_item"]


def test_topo_sort_breaks_cycle() -> None:
    order = topo_sort(
        ["a", "b", "c"],
        [("a", "b"), ("b", "c"), ("c", "a")],
    )
    assert len(order) == 3
    assert set(order) == {"a", "b", "c"}
