"""Interface-complete placeholder connectors (per docs/06 scope).

Snowflake, Trino, and BigQuery declare the contract but raise
ConnectorNotAvailableError with guidance until their implementations ship.
"""

from __future__ import annotations

import polars as pl

from ai_data_platform.connectors.base import (
    ConnectionResult,
    Connector,
    SampleBudget,
    TableSchema,
)
from ai_data_platform.core.exceptions import ConnectorNotAvailableError


class _PlaceholderConnector(Connector):
    coming: str = ""

    def _unavailable(self) -> ConnectorNotAvailableError:
        return ConnectorNotAvailableError(
            f"The {self.type_name} connector is not implemented yet ({self.coming}).",
            hint="Track progress on GitHub; CSV/Parquet/DuckDB/Postgres/MySQL work today.",
        )

    def test_connection(self) -> ConnectionResult:
        return ConnectionResult(ok=False, message=str(self._unavailable()))

    def list_schemas(self) -> list[str]:
        raise self._unavailable()

    def list_tables(self, schema: str | None = None) -> list[str]:
        raise self._unavailable()

    def get_table_schema(self, table: str) -> TableSchema:
        raise self._unavailable()

    def sample_data(self, table: str, budget: SampleBudget | None = None) -> pl.DataFrame:
        raise self._unavailable()


class SnowflakeConnector(_PlaceholderConnector):
    type_name = "snowflake"
    coming = "planned v0.2"


class TrinoConnector(_PlaceholderConnector):
    type_name = "trino"
    coming = "planned v0.2"


class BigQueryConnector(_PlaceholderConnector):
    type_name = "bigquery"
    coming = "planned v0.3"
