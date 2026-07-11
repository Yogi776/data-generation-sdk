# Load generated data to warehouses

Push FK-safe synthetic tables from `output/` to any [ingestr](https://github.com/bruin-data/ingestr)-supported destination.

## Install

```bash
pip install 'ai-data-platform[load]'
```

## Quick start

```bash
adp generate-data --rows 5000
adp load doctor
adp load
```

## adp.yaml reference

All parameters go under `destinations[].ingestr_options` in `adp.yaml`.
ADP converts snake_case keys to kebab-case ingestr flags automatically:

```
loader_file_size  →  --loader-file-size
extract_parallelism  →  --extract-parallelism
```

### Minimal config

```yaml
destinations:
  - name: snowflake_retail
    uri: ${SNOWFLAKE_URI}
    table_prefix: PUBLIC

load:
  default_destination: snowflake_retail
```

## Incremental strategies (batch CDC)

| `incremental_strategy` | Use case | Requires |
|---|---|---|
| `replace` (default) | Full synthetic refresh | — |
| `append` | Add rows | — |
| `merge` | Upsert by `primary_key` | `primary_key` column |
| `delete+insert` | Partitioned refresh with `incremental_key` | `incremental_key` column |

## Live source for CDC (`source:`)

By default, ADP loads from locally generated parquet files. To instead pull from a **live database** (e.g. migrate production Postgres → Snowflake), add a `source:` block to any destination. This routes ingestion through ingestr's source URI system instead of local files.

> **No `adp generate-data` needed** — ADP reads directly from the live source. Quality gate is skipped for live sources (use the source DB's own validation).

### Supported source schemes

Any [ingestr source](https://getbruin.com/docs/ingestr/supported-sources/) is supported. Common CDC sources:

| Scheme | Example URI |
|--------|-------------|
| `postgresql://` | `postgresql://user:pass@host:5432/prod` |
| `mysql://` | `mysql://user:pass@host:3306/app` |
| `snowflake://` | `snowflake://user:pass@account/db/schema` |
| `mongodb://` | `mongodb://user:pass@host:27017/app` |
| `bigquery://` | `bigquery://project?credentials_path=/creds.json` |

### Snowflake → Snowflake

Replicate between two Snowflake accounts/databases by setting `source.address` (read) and `sink.address` (write). Full example: [examples/snowflake-to-snowflake](../examples/snowflake-to-snowflake/).

**Pipeline format (recommended):**

```yaml
name: wf-sf-to-sf
version: v1
type: pipeline

pipeline:
  source:
    address: ${SNOWFLAKE_SOURCE_URI}
    incremental_key: updated_at
  sink:
    address: ${SNOWFLAKE_DEST_URI}
    table_prefix: PUBLIC
    incremental_strategy: merge
    primary_key: order_id
```

**Legacy `destinations:` format** still works — both compile to the same load plan.

```bash
adp apply-spec spec.yaml
adp load doctor
adp load
```

### Minimal config

```yaml
destinations:
  - name: prod_to_snowflake
    uri: ${SNOWFLAKE_URI}
    table_prefix: PUBLIC
    incremental_strategy: merge
    primary_key: order_id
    source:
      uri: postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:5432/prod_db
      incremental_key: updated_at
```

### Bounded extraction (time windows)

ingestr does not support a `--sql` flag. To filter source data, use `incremental_key` with `stream.interval_start` / `stream.interval_end`, or set `source.table` to a database view:

```yaml
source:
  uri: postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:5432/prod_db
  table: orders_apac_view          # pre-filtered view in the source DB
  incremental_key: updated_at
stream:
  interval_start: "2026-06-01"
  interval_end: "2026-07-01"
```

### Per-table source table mapping

By default, ADP uses the spec.yaml table name as the source table. Override with `table:`:

```yaml
source:
  uri: postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:5432/prod_db
  table: legacy_orders
  incremental_key: updated_at
```

### Full source block reference

```yaml
source:
  uri: postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:5432/prod_db
  table: orders
  incremental_key: updated_at
  # ingestr_options:
  #   page_size: 10000
  #   sql_limit: 100000
```

```yaml
# Example: merge (upsert) — update existing rows, insert new ones
destinations:
  - name: snowflake_retail
    uri: ${SNOWFLAKE_URI}
    table_prefix: PUBLIC
    incremental_strategy: merge
    primary_key: order_id       # must exist as a column in spec.yaml
```

```yaml
# Example: delete + insert — remove rows in a date window, reload them
destinations:
  - name: snowflake_retail
    uri: ${SNOWFLAKE_URI}
    table_prefix: PUBLIC
    incremental_strategy: delete+insert
    incremental_key: order_date  # DATE or DATETIME column in spec.yaml
```

### Time-windowed CDC (`interval_start` / `interval_end`)

For bounded incremental loads (e.g. reload only the last 30 days):

```yaml
destinations:
  - name: snowflake_retail
    uri: ${SNOWFLAKE_URI}
    table_prefix: PUBLIC
    incremental_strategy: delete+insert
    incremental_key: order_date
    stream:
      interval_start: "2026-06-01"
      interval_end: "2026-07-01"
```

ingestr translates `interval_start` / `interval_end` to `--interval-start` / `--interval-end` flags, which scope the `incremental_key` to a date/datetime window.

### Full ingestr_options reference

```yaml
destinations:
  - name: snowflake_retail
    uri: ${SNOWFLAKE_URI}
    table_prefix: PUBLIC

    # ── Incremental strategy ─────────────────────────────────
    incremental_strategy: replace

    # Primary key — required for merge strategy
    primary_key: null

    # Column to detect changes — required for delete+insert
    incremental_key: null

    # ── CDC / stream configuration (top-level) ──────────────
    # Stream mode: ingestr runs continuously, polling the source.
    # WARNING: blocks the CLI — use nohup or background for production.
    # stream:
    #   enabled: true
    #   flush_interval: "30s"         # flush to Snowflake every 30s
    #   flush_records: 50000          # OR flush after N records
    #   metrics_addr: "127.0.0.1:6060"   # expvar metrics endpoint
    #   interval_start: "2026-01-01"      # optional time window
    #   interval_end: "2026-07-01"

    # ── Performance: extract (reading parquet) ──────────────
    ingestr_options:

      # Parallel parquet readers. Default: 5. Range: 1–32.
      # Higher = faster extraction on multi-core machines.
      # Recommended: 8–16 for large files on modern hardware.
      extract_parallelism: 10

      # Partition source by a column and extract in parallel.
      # Dramatically faster for large fact tables with date key.
      # Value: column name (date, datetime, or integer).
      # extract_partition_by: order_date

      # Width of each extract partition window.
      # auto     : ingestr picks optimal splits (default)
      # 1h / 7d : fixed duration intervals
      # 10000    : integer step per partition
      # extract_partition_interval: auto

      # Rows per page when reading SQL sources (not parquet).
      # Default: 25000. Higher = fewer round-trips, more memory.
      # page_size: 25000

      # Maximum rows fetched from source (0 = unlimited).
      # sql_limit: 100000

      # Exclude columns from the source by name (comma-separated).
      # sql_exclude_columns: internal_id,raw_payload


      # ── Performance: load (writing to Snowflake) ───────────
      # Target rows per batch sent to Snowflake staging.
      # Default: 25000. Higher = fewer round-trips.
      # For 1M+ rows: 50000–100000 recommended.
      loader_file_size: 50000


      # ── Column transformation ──────────────────────────────
      # Rename or retype: 'col:TYPE', 'col:TYPE:src', 'col::src'
      # Available types: bigint, int, smallint, float, double,
      #   decimal(p,s), varchar(n), boolean, date, timestamp,
      #   timestamp_ntz, json, uuid, binary
      # Example: columns: "id:bigint,city::city_name,email:varchar(100)"
      # columns: null

      # Mask PII during load. Format: 'column:algorithm[:param]'
      # Algorithms:
      #   hash / sha256 / md5 / hmac     : deterministic hash
      #   email / phone / credit_card   : format-preserving mask
      #   ssn / redact                 : redact to [REDACTED]
      #   stars(n)                    : show first/last n chars
      #   fixed(value)                : constant value
      #   random(type,min,max)        : random within range
      #   partial(chars)              : keep first N chars
      #   first_letter / uuid / sequential / round / range
      #   date_shift / year_only / month_year
      # Example: mask: "email:hash,phone:redact,ssn:stars(4)"
      # mask: null

      # Trim whitespace from all string columns.
      # trim_whitespace: false


      # ── Snowflake: partitioning & clustering ───────────────
      # Partition key for destination table (ALTER TABLE … PARTITION BY).
      # partition_by: order_date

      # Clustering key(s) (ALTER TABLE … CLUSTER BY).
      # cluster_by: customer_id,order_date

      # Use cloud storage for staging instead of local temp.
      # Requires Snowflake storage integration configured.
      # staging_bucket: "s3://my-bucket/ingestr-staging/"
      # staging_bucket: "gs://my-bucket/ingestr-staging/"

      # Override the staging schema/dataset (default: same as dest).
      # staging_dataset: staging_schema


      # ── Schema evolution ─────────────────────────────────
      # evolve        : add new columns automatically (default)
      # freeze        : reject if source has extra columns
      # discard_row   : drop rows with extra columns
      # discard_value : set extra column values to NULL
      # schema_contract: evolve

      # Column naming in destination.
      # direct     : preserve original names
      # snake_case : convert to snake_case
      # auto       : detect from destination (default)
      # schema_naming: auto


      # ── Behaviour / safety ────────────────────────────────
      # Ignore previous load state; full refresh regardless.
      # full_refresh: false

      # Progress display: interactive / log / json
      # Note: ADP streams all ingestr output as live INFO logs,
      # so 'log' (default) or 'interactive' both show in real time.
      # progress: log

      # Directory for ingestr pipeline metadata (state, checksums).
      # Default: ~/.ingestr/
      # pipelines_dir: ./.ingestr/

      # Verbose debug output (HTTP calls, credentials, internals).
      # debug: false


      # ── Cost attribution ────────────────────────────────
      # JSON merged into Snowflake QUERY_TAG for cost tagging.
      # query_annotations: '{"project":"retail","env":"prod"}'
```

## Commands

```bash
adp generate-data --rows 5000
adp load doctor --destination snowflake_retail
adp load --dry-run
adp load
adp load --skip-quality        # skip DuckDB quality gate (faster re-runs)
adp load --tables fact_order,fact_order_item   # load subset only
adp load destinations
```

## Staging sources

| Format | Files | `--source-uri` |
|--------|-------|----------------|
| parquet (recommended) | `output/{table}.parquet` | `parquet:///path/to/{table}.parquet` |
| csv | `output/{table}.csv` | `csv:///path/to/{table}.csv` |
| duckdb | `output/generated.duckdb` | `duckdb:///{path}` (table name in `--source-table`) |

## Supported destinations

Run `adp load destinations` for the full list. 29 destinations including:
Snowflake, BigQuery, Postgres, Redshift, Databricks, DuckDB, MotherDuck, MySQL, MongoDB, ClickHouse, S3, GCS, Azure ADLS, and more.

## Performance tuning

| Knob | Default | Effect |
|------|---------|--------|
| `extract_parallelism` | 5 | More parallel parquet readers |
| `loader_file_size` | 25000 | Larger = fewer Snowflake round-trips |
| `extract_partition_by` | null | Date-based parallel extract (biggest win for large tables) |
| warehouse size | — | Biggest factor — use LARGE+ warehouse on Snowflake |

### Example: high-performance Snowflake load

```yaml
ingestr_options:
  extract_parallelism: 16
  loader_file_size: 100000
  # For date-partitioned large tables:
  # extract_partition_by: order_date
  # extract_partition_interval: auto
```

### Example: PII masking

```yaml
ingestr_options:
  columns: "email::email_addr,phone:redact"
  mask: "email:hash,phone:redact,ssn:stars(4)"
```

## Streaming CDC (`--stream`)

ingestr supports **continuous streaming ingestion** for CDC sources (Kafka, Debezium, PostgreSQL logical replication, etc.). When `stream.enabled: true`, ingestr runs as a long-lived process that polls the source and flushes to Snowflake on a schedule.

> **Warning:** Stream mode blocks the CLI. For production use, run with `nohup` or as a background service.

```yaml
destinations:
  - name: snowflake_retail
    uri: ${SNOWFLAKE_URI}
    table_prefix: PUBLIC
    incremental_strategy: merge
    primary_key: order_id
    stream:
      enabled: true
      flush_interval: "30s"
      flush_records: 50000
      metrics_addr: "127.0.0.1:6060"
      interval_start: "2026-01-01"
      interval_end: "2026-07-01"
```

**Note:** Stream mode requires a CDC-capable source (not local parquet files). For local parquet → Snowflake batch loads, use batch incremental strategies (`merge`, `append`, `delete+insert`) instead.

## Verifying CDC on Snowflake

Once data is loaded, verify change tracking directly in Snowflake:

```sql
-- Enable change tracking on a table
ALTER TABLE fact_order_item SET CHANGE_TRACKING = TRUE;

-- Query changes between two timestamps
SELECT * FROM TABLE(CHANGES(fact_order_item, START => '2026-07-09 00:00:00', END => '2026-07-10 00:00:00'));

-- Time travel — see table state at a past time
SELECT * FROM fact_order_item AT(TIMESTAMP => '2026-07-10 00:40:00'::timestamp);

-- Create a stream to track ongoing changes
CREATE TABLE fact_order_item_stream AS TABLE fact_order_item;
-- Then periodically:
-- SELECT * FROM fact_order_item_stream WHERE METADATA$ACTION = 'INSERT';
```

## License note

ingestr is FSL 1.1. Use as an optional ADP extra for pushing generated data; do not repackage as a competing ELT product.
