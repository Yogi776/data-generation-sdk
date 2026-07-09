"""Ingestion — Excel: multi-sheet workbooks, sheet selection, materialization."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_data_platform.ingestion import ingest_data
from ai_data_platform.ingestion.detector import excel_sheet_names

from _ingest_helpers import make_frame

pytest.importorskip("openpyxl")


def _workbook(path: Path) -> Path:
    import pandas as pd

    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        make_frame(120, seed=1).to_pandas().to_excel(xl, sheet_name="Orders", index=False)
        make_frame(30, seed=2).to_pandas().to_excel(xl, sheet_name="Returns", index=False)
    return path


def test_list_sheets(tmp_path: Path) -> None:
    wb = _workbook(tmp_path / "book.xlsx")
    assert excel_sheet_names(str(wb)) == ["Orders", "Returns"]


def test_ingest_default_first_sheet(tmp_path: Path) -> None:
    wb = _workbook(tmp_path / "book.xlsx")
    r = ingest_data(str(wb), table_name="book", options={"project": str(tmp_path)})
    assert r["detected_format"] == "excel"
    assert r["relation_kind"] == "table"  # Excel must be materialized
    assert r["row_count"] == 120
    assert r["sheet_used"] == "Orders"
    assert r["excel_sheets"] == ["Orders", "Returns"]


def test_ingest_sheet_by_name(tmp_path: Path) -> None:
    wb = _workbook(tmp_path / "book.xlsx")
    r = ingest_data(str(wb), table_name="returns", options={"project": str(tmp_path), "sheet": "Returns"})
    assert r["row_count"] == 30
    assert r["sheet_used"] == "Returns"


def test_ingest_sheet_by_index(tmp_path: Path) -> None:
    wb = _workbook(tmp_path / "book.xlsx")
    r = ingest_data(str(wb), table_name="second", options={"project": str(tmp_path), "sheet": 1})
    assert r["sheet_used"] == "Returns"
