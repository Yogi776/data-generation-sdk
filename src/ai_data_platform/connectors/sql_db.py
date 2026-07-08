"""SQL database connectors (PostgreSQL, MySQL) via SQLAlchemy engines.

Credentials come from `dsn` with ${ENV_VAR} interpolation — never plaintext.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ai_data_platform.connectors.base import (
    Capabilities,
    ColumnSchema,
    ConnectionResult,
    Connector,
    SampleBudget,
    TableSchema,
    normalize_dtype,
)
from ai_data_platform.core.exceptions import (
    ConnectorError,
    ConnectorNotAvailableError,
    TableNotFoundError,
)


class _SQLConnector(Connector):
    driver_package: str = ""
    extra: str = ""
    dialect_prefix: str = ""

    def _engine(self) -> Engine:
        dsn = self.source.resolved_dsn()
        if not dsn:
            raise ConnectorError(
                f"Source {self.source.name!r} has no `dsn` configured.",
                hint='Example: dsn: "postgresql+psycopg://user:${PGPASSWORD}@host:5432/db"',
            )
        try:
            __import__(self.driver_package)
        except ImportError as e:
            raise ConnectorNotAvailableError(
                f"{self.type_name} support requires the {self.driver_package!r} driver.",
                hint=f"pip install 'ai-data-platform[{self.extra}]'",
            ) from e
        try:
            return create_engine(dsn, pool_pre_ping=True)
        except Exception as e:
            raise ConnectorError(f"Invalid DSN for source {self.source.name!r}: {e}") from e

    def _default_schema(self) -> str:
        return self.source.schema_name or ("public" if self.type_name == "postgres" else "")

    # -- contract -----------------------------------------------------------
    def test_connection(self) -> ConnectionResult:
        try:
            with self._engine().connect() as conn:
                ver = conn.execute(text("select version()")).scalar()
            return ConnectionResult(ok=True, message="Connected.", server_version=str(ver))
        except ConnectorError as e:
            return ConnectionResult(ok=False, message=str(e))
        except Exception as e:  # driver-level errors
            return ConnectionResult(ok=False, message=f"Connection failed: {e}")

    def list_schemas(self) -> list[str]:
        q = text(
            "select schema_name from information_schema.schemata "
            "where schema_name not in ('information_schema','pg_catalog','pg_toast',"
            "'mysql','performance_schema','sys') order by 1"
        )
        with self._engine().connect() as conn:
            return [r[0] for r in conn.execute(q)]

    def list_tables(self, schema: str | None = None) -> list[str]:
        schema = schema or self._default_schema()
        q = text(
            "select table_name from information_schema.tables "
            "where table_type = 'BASE TABLE' and table_schema = :s order by 1"
        )
        with self._engine().connect() as conn:
            return [r[0] for r in conn.execute(q, {"s": schema})]

    def get_table_schema(self, table: str) -> TableSchema:
        schema = self._default_schema()
        q = text(
            "select column_name, data_type, is_nullable, ordinal_position "
            "from information_schema.columns "
            "where table_schema = :s and table_name = :t order by ordinal_position"
        )
        with self._engine().connect() as conn:
            rows: list[Any] = list(conn.execute(q, {"s": schema, "t": table}))
        if not rows:
            raise TableNotFoundError(table)
        cols = tuple(
            ColumnSchema(
                name=r[0],
                data_type=normalize_dtype(str(r[1])),
                nullable=str(r[2]).upper() == "YES",
                ordinal=int(r[3]) - 1,
            )
            for r in rows
        )
        return TableSchema(name=table, columns=cols, schema_name=schema)

    def sample_data(self, table: str, budget: SampleBudget | None = None) -> pl.DataFrame:
        budget = budget or SampleBudget()
        schema = self._default_schema()
        # identifier safety: table must exist in information_schema first
        self.get_table_schema(table)
        qualified = f'"{schema}"."{table}"' if self.type_name == "postgres" else f"`{table}`"
        query = f"select * from {qualified} limit {int(budget.rows)}"  # noqa: S608 - verified ident
        try:
            return pl.read_database(query, connection=self._engine())
        except Exception as e:
            raise ConnectorError(f"Sampling {table!r} failed: {e}") from e


class PostgresConnector(_SQLConnector):
    type_name = "postgres"
    driver_package = "psycopg"
    extra = "postgres"
    capabilities = Capabilities(
        supports_incremental=True, supports_pushdown_profiling=True, dialect="postgres"
    )


class MySQLConnector(_SQLConnector):
    type_name = "mysql"
    driver_package = "pymysql"
    extra = "mysql"
    capabilities = Capabilities(supports_incremental=True, dialect="mysql")
