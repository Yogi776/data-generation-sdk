"""Universal, metadata-driven data ingestion on DuckDB.

Point :func:`ingest_data` at a file, folder, URL, or cloud path and it detects
the format, infers the schema, profiles the data, flags quality issues, creates a
queryable DuckDB view/table, and returns a full metadata report — with no domain
logic hardcoded, so it works for any industry.

    from ai_data_platform.ingestion import ingest_data
    report = ingest_data("./data/orders.csv", table_name="orders")

The engine is standalone: it manages its own DuckDB database
(``.adp/ingestion.duckdb``) and metadata registry, independent of the rest of the
platform.
"""

from ai_data_platform.ingestion.engine import IngestionEngine, ingest_data

__all__ = ["IngestionEngine", "ingest_data"]
