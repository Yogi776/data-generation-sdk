"""Metadata catalog of ingestr-supported load destinations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DestinationInfo:
    id: str
    label: str
    scheme: str
    doc_url: str
    example_uri: str
    common_options: tuple[str, ...] = ()


INGESTR_DESTINATIONS: tuple[DestinationInfo, ...] = (
    DestinationInfo("athena", "AWS Athena", "athena://", "https://getbruin.com/docs/ingestr/supported-sources/athena.html", "athena://?region=us-east-1"),
    DestinationInfo("iceberg", "Apache Iceberg", "iceberg://", "https://getbruin.com/docs/ingestr/", "iceberg://catalog/db/table"),
    DestinationInfo("redshift", "AWS Redshift", "redshift://", "https://getbruin.com/docs/ingestr/supported-sources/redshift.html", "redshift://${USER}:${PASSWORD}@${HOST}:5439/${DB}"),
    DestinationInfo("cassandra", "Cassandra", "cassandra://", "https://getbruin.com/docs/ingestr/", "cassandra://${HOST}"),
    DestinationInfo("clickhouse", "ClickHouse", "clickhouse://", "https://getbruin.com/docs/ingestr/supported-sources/clickhouse.html", "clickhouse://${USER}:${PASSWORD}@${HOST}:8123/${DB}"),
    DestinationInfo("cratedb", "CrateDB", "cratedb://", "https://getbruin.com/docs/ingestr/", "cratedb://${HOST}"),
    DestinationInfo("databricks", "Databricks", "databricks://", "https://getbruin.com/docs/ingestr/supported-sources/databricks.html", "databricks://${TOKEN}@${HOST}"),
    DestinationInfo("duckdb", "DuckDB", "duckdb:///", "https://getbruin.com/docs/ingestr/supported-sources/duckdb.html", "duckdb:///${PATH}/warehouse.duckdb"),
    DestinationInfo("dynamodb", "DynamoDB", "dynamodb://", "https://getbruin.com/docs/ingestr/", "dynamodb://?region=us-east-1"),
    DestinationInfo("elasticsearch", "Elasticsearch", "elasticsearch://", "https://getbruin.com/docs/ingestr/", "elasticsearch://${HOST}"),
    DestinationInfo("bigquery", "Google BigQuery", "bigquery://", "https://getbruin.com/docs/ingestr/supported-sources/bigquery.html", "bigquery://${PROJECT}?credentials_path=${GOOGLE_APPLICATION_CREDENTIALS}", ("staging-bucket",)),
    DestinationInfo("csv", "Local CSV", "csv://", "https://getbruin.com/docs/ingestr/", "csv:///path/to/file.csv"),
    DestinationInfo("maxcompute", "MaxCompute", "maxcompute://", "https://getbruin.com/docs/ingestr/", "maxcompute://${PROJECT}"),
    DestinationInfo("fabric", "Microsoft Fabric", "fabric://", "https://getbruin.com/docs/ingestr/", "fabric://${WORKSPACE}"),
    DestinationInfo("onelake", "Microsoft OneLake", "onelake://", "https://getbruin.com/docs/ingestr/", "onelake://${WORKSPACE}"),
    DestinationInfo("mssql", "Microsoft SQL Server", "mssql://", "https://getbruin.com/docs/ingestr/supported-sources/mssql.html", "mssql://${USER}:${PASSWORD}@${HOST}:1433/${DB}"),
    DestinationInfo("mongodb", "MongoDB", "mongodb://", "https://getbruin.com/docs/ingestr/supported-sources/mongodb.html", "mongodb://${USER}:${PASSWORD}@${HOST}:27017/${DB}"),
    DestinationInfo("motherduck", "MotherDuck", "motherduck://", "https://getbruin.com/docs/ingestr/supported-sources/motherduck.html", "motherduck:///${TOKEN}"),
    DestinationInfo("mysql", "MySQL", "mysql://", "https://getbruin.com/docs/ingestr/supported-sources/mysql.html", "mysql://${USER}:${PASSWORD}@${HOST}:3306/${DB}"),
    DestinationInfo("planetscale", "PlanetScale", "mysql://", "https://getbruin.com/docs/ingestr/supported-sources/planetscale.html", "mysql://${USER}:${PASSWORD}@${HOST}/${DB}"),
    DestinationInfo("postgres", "Postgres", "postgresql://", "https://getbruin.com/docs/ingestr/supported-sources/postgres.html", "postgresql://${USER}:${PASSWORD}@${HOST}:5432/${DB}"),
    DestinationInfo("snowflake", "Snowflake", "snowflake://", "https://getbruin.com/docs/ingestr/supported-sources/snowflake.html", "snowflake://${USER}:${PASSWORD}@${ACCOUNT}/${DB}/${SCHEMA}?warehouse=${WH}&role=${ROLE}"),
    DestinationInfo("sqlite", "SQLite", "sqlite:///", "https://getbruin.com/docs/ingestr/supported-sources/sqlite.html", "sqlite:///${PATH}/db.sqlite"),
    DestinationInfo("starrocks", "StarRocks", "starrocks://", "https://getbruin.com/docs/ingestr/", "starrocks://${HOST}"),
    DestinationInfo("synapse", "Microsoft Synapse", "synapse://", "https://getbruin.com/docs/ingestr/", "synapse://${WORKSPACE}"),
    DestinationInfo("trino", "Trino", "trino://", "https://getbruin.com/docs/ingestr/supported-sources/trino.html", "trino://${USER}@${HOST}:8080/${CATALOG}"),
    DestinationInfo("s3", "Amazon S3", "s3://", "https://getbruin.com/docs/ingestr/supported-sources/s3.html", "s3://?access_key_id=${AWS_KEY}&secret_access_key=${AWS_SECRET}&bucket=${BUCKET}"),
    DestinationInfo("gcs", "Google Cloud Storage", "gs://", "https://getbruin.com/docs/ingestr/supported-sources/gcs.html", "gs://?credentials_path=${GOOGLE_APPLICATION_CREDENTIALS}&bucket=${BUCKET}"),
    DestinationInfo("adls", "Azure Data Lake Gen2", "adls://", "https://getbruin.com/docs/ingestr/", "adls://${ACCOUNT}.dfs.core.windows.net"),
)


def lookup_by_scheme(scheme: str) -> list[DestinationInfo]:
    prefix = scheme if scheme.endswith("://") else f"{scheme}://"
    return [d for d in INGESTR_DESTINATIONS if d.scheme.startswith(prefix.split("://")[0])]


def lookup_uri(uri: str) -> DestinationInfo | None:
    for d in INGESTR_DESTINATIONS:
        if uri.startswith(d.scheme.split("://")[0] + "://"):
            return d
    return None
