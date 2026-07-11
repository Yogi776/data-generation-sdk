# Snowflake → Snowflake

Replicate or migrate tables from one Snowflake database to another using ADP + [ingestr](https://github.com/bruin-data/ingestr). No synthetic generation step — data flows directly source → destination.

## When to use

| Scenario | `incremental_strategy` |
|----------|--------------------------|
| Clone prod → dev (full refresh) | `replace` |
| Nightly upsert of changed rows | `merge` + `primary_key` + `source.incremental_key` |
| Reload a date partition | `delete+insert` + `incremental_key` + `stream.interval_*` |

## Quick start

```bash
cd examples/snowflake-to-snowflake
cp .env.example .env          # set SNOWFLAKE_SOURCE_URI and SNOWFLAKE_DEST_URI
adp apply-spec spec.yaml      # register table list + PKs in catalog
adp load doctor               # verify URIs and ingestr
adp load --dry-run            # preview ingestr commands
adp load                      # run replication
```

## adp.yaml (pipeline format)

Simple **source → sink** layout (legacy `destinations:` still supported):

```yaml
name: wf-sf-to-sf
version: v1
type: pipeline
tags:
  - snowflake
  - replication

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

DataOS-style `workflow.dag[].spec.stackSpec` is also accepted — k8s/compute fields are ignored:

```yaml
workflow:
  dag:
    - name: sf-account
      spec:
        stackSpec:
          source:
            address: salesforce://?username=${SF_USER}
            options:
              source-table: account
          sink:
            address: ${SNOWFLAKE_DEST_URI}
            options:
              dest-table: PUBLIC.account
              incremental-strategy: merge
```

Load a subset:

```bash
adp load --tables dim_customer,fact_order
```

## URI reference

Both source and destination use the same ingestr Snowflake URI shape:

```
snowflake://USER:PASSWORD@ACCOUNT_IDENTIFIER/DATABASE/SCHEMA?warehouse=WH&role=ROLE
```

| Component | Example |
|-----------|---------|
| Account | `xy12345.us-east-1` or `orgname-accountname` |
| Database / schema | In path: `/PROD_DB/PUBLIC` |
| Warehouse / role | Query params: `?warehouse=COMPUTE_WH&role=LOADER` |

**Docs:** [ingestr Snowflake source](https://getbruin.com/docs/ingestr/supported-sources/snowflake.html)

Use separate env vars so source (read-only role) and destination (write role) credentials never share one URI.

## Table name mapping

| Case | Config |
|------|--------|
| Same name in source & dest | Omit `tables:` — uses `table_prefix.{spec_name}` |
| Different dest object names | `destinations[].tables: { spec_name: DEST_SCHEMA.TABLE }` |
| Single source table override | `source.table:` (applies to **all** tables — use only for 1-table loads) |

Source table names default to spec table names (`dim_customer`, `fact_order`). Ensure they exist in the URI schema or override with `source.table` for single-table jobs.

## Full refresh example

```yaml
destinations:
  - name: sf_clone
    uri: ${SNOWFLAKE_DEST_URI}
    table_prefix: PUBLIC
    incremental_strategy: replace
    source:
      uri: ${SNOWFLAKE_SOURCE_URI}
```

## Incremental merge example

```yaml
destinations:
  - name: sf_cdc
    uri: ${SNOWFLAKE_DEST_URI}
    table_prefix: PUBLIC
    incremental_strategy: merge
    primary_key: order_id
    source:
      uri: ${SNOWFLAKE_SOURCE_URI}
      incremental_key: updated_at
```

## Verify on destination

```sql
SELECT COUNT(*) FROM PUBLIC.fact_order;
SELECT MAX(updated_at) FROM PUBLIC.fact_order;
```

## See also

- [LOAD.md](../../docs/LOAD.md) — live source (`source:`) and incremental strategies
- [examples/retail](../retail/) — local parquet → Snowflake (generate then load)
