"""DuckDB connector: local analytical database files."""

from __future__ import annotations

from pathlib import Path

import duckdb
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

_IDENT_OK = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _quote_ident(name: str) -> str:
    if not name or not set(name) <= _IDENT_OK:
        # double-quote and escape embedded quotes
        return '"' + name.replace('"', '""') + '"'
    return name


class DuckDBConnector(Connector):
    type_name = "duckdb"
    capabilities = Capabilities(
        supports_pushdown_profiling=True, max_sample_rows=1_000_000, dialect="duckdb"
    )

    def _connect(self) -> duckdb.DuckDBPyConnection:
        if not self.source.path:
            raise ConnectorError(
                f"Source {self.source.name!r} has no `path` to a .duckdb file.",
                hint="Set `path:` in adp.yaml.",
            )
        path = Path(self.source.path).expanduser()
        if not path.exists():
            raise ConnectorError(
                f"DuckDB file {path} does not exist.",
                hint="Check the `path:` for this source in adp.yaml.",
            )
        return duckdb.connect(str(path), read_only=True)

    def test_connection(self) -> ConnectionResult:
        try:
            with self._connect() as con:
                version = con.execute("select version()").fetchone()
                ver = str(version[0]) if version else None
            return ConnectionResult(ok=True, message="Connected.", server_version=ver)
        except (ConnectorError, duckdb.Error) as e:
            return ConnectionResult(ok=False, message=str(e))

    def list_schemas(self) -> list[str]:
        with self._connect() as con:
            rows = con.execute(
                "select distinct table_schema from information_schema.tables order by 1"
            ).fetchall()
        return [r[0] for r in rows]

    def list_tables(self, schema: str | None = None) -> list[str]:
        schema = schema or "main"
        with self._connect() as con:
            rows = con.execute(
                "select table_name from information_schema.tables "
                "where table_schema = ? order by 1",
                [schema],
            ).fetchall()
        return [r[0] for r in rows]

    def get_table_schema(self, table: str) -> TableSchema:
        with self._connect() as con:
            rows = con.execute(
                "select column_name, data_type, is_nullable, ordinal_position "
                "from information_schema.columns where table_name = ? "
                "order by ordinal_position",
                [table],
            ).fetchall()
            if not rows:
                raise TableNotFoundError(table)
            count = con.execute(
                f"select count(*) from {_quote_ident(table)}"  # noqa: S608 - ident quoted
            ).fetchone()
        cols = tuple(
            ColumnSchema(
                name=r[0],
                data_type=normalize_dtype(str(r[1])),
                nullable=str(r[2]).upper() == "YES",
                ordinal=int(r[3]) - 1,
            )
            for r in rows
        )
        return TableSchema(
            name=table,
            columns=cols,
            schema_name="main",
            row_count=int(count[0]) if count else None,
        )

    def sample_data(self, table: str, budget: SampleBudget | None = None) -> pl.DataFrame:
        budget = budget or SampleBudget()
        ident = _quote_ident(table)
        order = "using sample" if budget.method == "random" else ""
        with self._connect() as con:
            try:
                if budget.method == "random":
                    rel = con.execute(
                        f"select * from {ident} using sample {budget.rows} rows"  # noqa: S608
                    )
                else:
                    rel = con.execute(f"select * from {ident} limit {int(budget.rows)}")  # noqa: S608
                return rel.pl()
            except duckdb.Error as e:
                raise ConnectorError(f"Sampling {table!r} failed: {e} {order}") from e
