"""File connectors: CSV and Parquet.

`path` may point to a single file (one table, named after the file stem) or a
directory (one table per file).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from ai_data_platform.connectors.base import (
    Capabilities,
    ColumnSchema,
    ConnectionResult,
    Connector,
    SampleBudget,
    TableSchema,
    normalize_dtype,
)
from ai_data_platform.core.exceptions import ConnectorError, TableNotFoundError


class _FileConnector(Connector):
    suffix: str = ""
    capabilities = Capabilities(max_sample_rows=1_000_000, dialect="duckdb")

    def _root(self) -> Path:
        if not self.source.path:
            raise ConnectorError(
                f"Source {self.source.name!r} has no `path` configured.",
                hint="Set `path:` to a file or directory in adp.yaml.",
            )
        return Path(self.source.path).expanduser()

    def _files(self) -> dict[str, Path]:
        root = self._root()
        if root.is_file():
            return {root.stem: root}
        if root.is_dir():
            return {p.stem: p for p in sorted(root.glob(f"*{self.suffix}"))}
        raise ConnectorError(
            f"Path {root} does not exist.",
            hint="Check the `path:` for this source in adp.yaml.",
        )

    def _read(self, path: Path, n_rows: int | None = None) -> pl.DataFrame:
        raise NotImplementedError

    # -- contract -----------------------------------------------------------
    def test_connection(self) -> ConnectionResult:
        try:
            files = self._files()
        except ConnectorError as e:
            return ConnectionResult(ok=False, message=str(e))
        if not files:
            return ConnectionResult(ok=False, message=f"No {self.suffix} files found.")
        return ConnectionResult(ok=True, message=f"{len(files)} table(s) found.")

    def list_schemas(self) -> list[str]:
        return ["main"]

    def list_tables(self, schema: str | None = None) -> list[str]:
        return list(self._files().keys())

    def get_table_schema(self, table: str) -> TableSchema:
        files = self._files()
        if table not in files:
            raise TableNotFoundError(table)
        df = self._read(files[table], n_rows=100)
        cols = tuple(
            ColumnSchema(name=c, data_type=normalize_dtype(str(dt)), ordinal=i)
            for i, (c, dt) in enumerate(df.schema.items())
        )
        return TableSchema(name=table, columns=cols, schema_name="main")

    def sample_data(self, table: str, budget: SampleBudget | None = None) -> pl.DataFrame:
        budget = budget or SampleBudget()
        files = self._files()
        if table not in files:
            raise TableNotFoundError(table)
        df = self._read(files[table], n_rows=None)
        if len(df) <= budget.rows:
            return df
        if budget.method == "random":
            return df.sample(n=budget.rows, seed=0)
        return df.head(budget.rows)


class CSVConnector(_FileConnector):
    type_name = "csv"
    suffix = ".csv"

    def _read(self, path: Path, n_rows: int | None = None) -> pl.DataFrame:
        try:
            return pl.read_csv(path, n_rows=n_rows, try_parse_dates=True)
        except Exception as e:
            raise ConnectorError(f"Failed to read CSV {path}: {e}") from e


class ParquetConnector(_FileConnector):
    type_name = "parquet"
    suffix = ".parquet"

    def _read(self, path: Path, n_rows: int | None = None) -> pl.DataFrame:
        try:
            df = pl.read_parquet(path)
        except Exception as e:
            raise ConnectorError(f"Failed to read Parquet {path}: {e}") from e
        return df.head(n_rows) if n_rows else df
