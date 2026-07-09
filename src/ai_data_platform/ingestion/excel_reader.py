"""Excel adapter.

DuckDB cannot read .xls/.xlsx natively without the (optional) spatial/excel
extension, so Excel is handled in Python via pandas + openpyxl (xlsx) / xlrd
(legacy xls) and handed to DuckDB as an Arrow table. Supports multi-sheet
workbooks and explicit sheet selection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa

from ai_data_platform.core.exceptions import FormatDependencyError, IngestionError
from ai_data_platform.ingestion.detector import excel_sheet_names


def read_excel(path: str, options: dict[str, Any] | None = None) -> tuple[pa.Table, str, list[str]]:
    """Read one sheet of an Excel workbook into an Arrow table.

    Returns ``(table, sheet_used, all_sheets)``. Sheet selection precedence:
    ``options['sheet']`` (name or 0-based index) → first sheet.
    """
    options = options or {}
    p = Path(path).expanduser()
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        raise FormatDependencyError(
            "excel", "Install the ingest extra: pip install 'ai-data-platform[ingest]'"
        ) from e

    sheets = excel_sheet_names(str(p))
    if not sheets:
        raise IngestionError(f"No sheets found in {p}.")

    requested = options.get("sheet")
    sheet: str | int
    if requested is None:
        sheet = sheets[0]
    elif isinstance(requested, int):
        if requested >= len(sheets):
            raise IngestionError(f"Sheet index {requested} out of range (have {len(sheets)}).")
        sheet = sheets[requested]
    else:
        if requested not in sheets:
            raise IngestionError(
                f"Sheet {requested!r} not found.", hint=f"Available: {', '.join(sheets)}."
            )
        sheet = requested

    header = 0 if options.get("has_header", True) else None
    engine = "openpyxl" if p.suffix.lower() in (".xlsx", ".xlsm") else None
    try:
        df = pd.read_excel(p, sheet_name=sheet, header=header, engine=engine)
    except ImportError as e:  # legacy .xls needs xlrd
        raise FormatDependencyError(
            "xls", "Legacy .xls needs xlrd: pip install xlrd"
        ) from e
    except Exception as e:  # noqa: BLE001
        raise IngestionError(f"Failed to read sheet {sheet!r} from {p}: {e}") from e

    # Normalize column names to strings (pandas may infer ints for headerless).
    df.columns = [str(c) for c in df.columns]
    return pa.Table.from_pandas(df, preserve_index=False), str(sheet), sheets
