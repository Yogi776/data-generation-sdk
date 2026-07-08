"""Connector registry: type name -> lazy-imported implementation."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from ai_data_platform.connectors.base import Connector, ConnectorInfo
from ai_data_platform.core.exceptions import ConnectorError

if TYPE_CHECKING:  # pragma: no cover
    from ai_data_platform.config import SourceConfig

REGISTRY: dict[str, ConnectorInfo] = {
    "csv": ConnectorInfo("csv", "ai_data_platform.connectors.files", "CSVConnector"),
    "parquet": ConnectorInfo("parquet", "ai_data_platform.connectors.files", "ParquetConnector"),
    "duckdb": ConnectorInfo("duckdb", "ai_data_platform.connectors.duckdb_conn", "DuckDBConnector"),
    "postgres": ConnectorInfo(
        "postgres", "ai_data_platform.connectors.sql_db", "PostgresConnector", extra="postgres"
    ),
    "mysql": ConnectorInfo(
        "mysql", "ai_data_platform.connectors.sql_db", "MySQLConnector", extra="mysql"
    ),
    "snowflake": ConnectorInfo(
        "snowflake",
        "ai_data_platform.connectors.placeholders",
        "SnowflakeConnector",
        extra="snowflake",
        placeholder=True,
    ),
    "trino": ConnectorInfo(
        "trino",
        "ai_data_platform.connectors.placeholders",
        "TrinoConnector",
        extra="trino",
        placeholder=True,
    ),
    "bigquery": ConnectorInfo(
        "bigquery",
        "ai_data_platform.connectors.placeholders",
        "BigQueryConnector",
        extra="bigquery",
        placeholder=True,
    ),
}


def get_connector(source: SourceConfig) -> Connector:
    """Instantiate the connector for a configured source."""
    info = REGISTRY.get(source.type)
    if info is None:
        raise ConnectorError(
            f"Unknown source type {source.type!r}.",
            hint=f"Supported types: {', '.join(sorted(REGISTRY))}",
        )
    module = import_module(info.module)
    cls: type[Connector] = getattr(module, info.class_name)
    return cls(source)


__all__ = ["REGISTRY", "Connector", "get_connector"]
