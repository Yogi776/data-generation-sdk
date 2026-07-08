# Agent Skills Map — 15-skill taxonomy vs implementation

How the proposed agent skill set maps to what's built. "MCP surface" = how an
agent (Cursor/Claude/ChatGPT) reaches it today.

| # | Skill | Status | Where it lives | MCP surface |
|---|---|---|---|---|
| 1 | domain-researcher | ✅ via client + prompt | Client agent's web search, orchestrated by the `research_and_generate` prompt (research → cite → encode) | prompt `research_and_generate` |
| 2 | prompt-to-data-spec | ✅ | `spec.py::propose_spec` — LLM drafts spec from description + research notes, schema-validated with retry | tool `propose_spec` |
| 3 | data-model-designer | ✅ | Spec language: tables, PK/FK, 3 join cardinalities, dims/facts detected by `semantic/builder` | tools `apply_spec`, `create_semantic_model` |
| 4 | schema-profiler (metadata analysis) | ✅ | `metadata/scan` + `profiler` — entities, PK/FK inference with confidence, cardinality, PII | tools `scan_sources`, `profile_source`, `get_table_schema`, `search_metadata` |
| 5 | synthetic-data-generator | ✅ | Plan-IR engine: FK-safe, seeded, chunked; csv/parquet/json*/sql/duckdb (*json via duckdb export) | tool `generate_synthetic_data` |
| 6 | constraint-validator | ✅ | Engine guarantees (PK unique, FK zero-orphan, 1:1 permutation) + dependency engine (`after`, `expr`, `null_unless`, `values_by`) | enforced in generation; verified by `run_quality_check` |
| 7 | data-quality-checker | ✅ | `quality/checks` — derived rules, weighted explained score, evidence | tool `run_quality_check` |
| 8 | distribution-realism | ✅ | Profiled/declared weights, moment-matched lognormal, Poisson, hierarchies, sparsity; research-grounded via propose_spec | spec fields + `propose_spec` |
| 9 | privacy-safe-generator | ✅ | PII 3-signal detection; never copies source values (verified 0-leak); name/email samplers generate fake-but-realistic PII; PII columns never reach LLMs | automatic in profile/generate |
| 10 | semantic-model-builder | ✅ | Generic + Cube.js renderers | tool `create_semantic_model` |
| 11 | database-connector | ◐ partial | Postgres, MySQL, DuckDB, CSV, Parquet live; Snowflake/Trino/BigQuery interface-complete placeholders; S3/Iceberg/Databricks roadmap | `adp connect` (config), then scan tools |
| 12 | large-scale-generator | ◐ partial | Chunked streaming (100k/chunk), 200k rows/2s locally; TB-scale is the platform Go tier (ADR-0010, Plan IR ready) | tool capped at 1M rows/call; CLI unlimited |
| 13 | industry-rules-engine | ◐ partial | Rules are declarative per-spec (any domain, proven retail/healthcare); *packaged* per-industry rule libraries (KYC flows, HIPAA field sets) = platform knowledge packs (M3/M9) | via spec dependencies today |
| 14 | schema-evolution | ◔ minimal | Catalog is versioned (`schema_version`, fingerprints); dataset versioning/compat migration not yet | roadmap |
| 15 | scenario-generator (churn/fraud/pump-failure) | ◔ minimal | Fraud/anomaly rates declarable (`fraud_flag` weights); labeled scenario patterns (churn cohorts, failure precursors) = roadmap | via spec today |
| — | test-case-generator | ◔ | Platform M5 scope (docs/03 `generate_test_cases`) | roadmap |

**MVP-6 verdict:** all six MVP skills (prompt-to-data-spec, domain-researcher,
data-model-designer, synthetic-data-generator, constraint-validator,
data-quality-checker) are implemented and live-verified end to end.

## Correctness guarantees ("values and primary keys are real")

| Guarantee | Mechanism | Verified |
|---|---|---|
| PKs real & unique | uuid4 / monotonic sequence, never sampled | 50k/50k unique, tested |
| FKs real | drawn from actual generated parent keys | 0 orphans, tested |
| Names/emails realistic | name-based samplers (real name lists, emails derived from names) — propose_spec now instructs the LLM to rely on them, never `format`, for person fields | preview check |
| Codes/IDs shaped | `format` templates for order/tracking/MRN codes | regex-tested |
| Amounts realistic | moment-matched lognormal from research/profile | Δ≤2% vs targets |
| No real PII ever | source values never copied (0-leak test); PII generated synthetically | tested |
