# Architecture — ai-data-platform

> Companion to the README. Covers the complete architecture, how domain-generality
> is achieved, exactly where customization is (and isn't) required, and every
> extension point.

---

## 1. Design principle

**Nothing domain-specific lives in source code.** Every capability derives from
metadata the platform discovers about *your* data:

```
your data ──scan──▶ catalog (schema, keys, relationships)
           ──profile──▶ statistics (distributions, categories, PII, confidence)
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
   generator             quality engine        semantic builder
 (samplers compiled    (checks derived        (facts/dims/measures
  from profiles)        from metadata)         detected from shape)
```

There is no `if domain == "healthcare"` anywhere. Healthcare, retail, finance,
manufacturing, logistics — all flow through the same inference. This claim is
enforced by tests (`tests/test_e2e_retail.py`) and by review policy.

## 2. System architecture

```
┌────────────────────── Interfaces (thin adapters, zero logic) ─────────────────────┐
│  CLI (Typer, `adp`)   REST API (FastAPI)   Web UI (static page)   MCP (stdio)     │
└──────────────────────────────────┬────────────────────────────────────────────────┘
                                   ▼
                     ADPClient  (sdk.py — the ONLY backend)
                                   │
   ┌──────────┬───────────┬────────┼─────────┬───────────┬──────────┬─────────┐
   ▼          ▼           ▼        ▼         ▼           ▼          ▼         ▼
connectors  metadata   profiler  generator  quality   semantic     sql      docs
(SDK +      (catalog:  (stats,   (plan IR + (derived  (fact/dim → (NL→SQL,  (data
 registry)  SQLite +   PII,      samplers,  checks +  generic/     guarded)  dict)
            SQLAlchemy) PK/FK)   FK-safe)   score)    Cube YAML)
   │                                   │                              │
   ▼                                   ▼                              ▼
 sources                       output/ (csv, parquet,          LLM providers
 (csv, parquet, duckdb,        duckdb, sql)                    (MiniMax default,
  postgres, mysql, …)                                           OpenAI/Anthropic/
                                                                Gemini/local stub)
Cross-cutting: config (adp.yaml + env interpolation) · typed exceptions with hints
· masked logging · safe project-rooted writes
```

**Key invariants**

1. **One backend, many faces** — CLI, API, UI, and MCP all call `ADPClient`;
   fixing a bug once fixes it everywhere.
2. **Plan IR** — generation compiles to a language-neutral JSON plan
   (`plan_ir_version`, per-table samplers, FK strategies, seeds). Any conformant
   executor can run it; the platform's future Go workers (ADR-0010) drop in
   without redesign.
3. **Determinism** — same catalog version + seed ⇒ byte-identical output
   (per-partition seeded PRNG: `sha256(seed, table, chunk)`).
4. **Confidence + provenance** — inferences (FKs, PII, table kinds) carry
   confidence scores and evidence; user statements outrank inferences.
5. **Read-only against your sources** — connectors sample with budgets;
   NL→SQL executes through a SELECT-only guard; writes land only inside the
   project directory (path-traversal rejected).

## 3. The pipeline in detail

| Stage | What happens | Domain knowledge used |
|---|---|---|
| `adp scan` | Connector lists tables/columns/types → catalog; FK candidates from naming conventions (`customer_id` → `customers`), capped at 0.6 confidence | None — structural |
| `adp profile` | Polars over budgeted samples: nulls, distincts, min/max/mean/std, top values, entropy; PII 3-signal classification; PK by uniqueness ≥ 0.999; FK confirmed by inclusion ≥ 0.95 | None — statistical |
| `adp generate-data` | Plan IR compiled: PKs → sequences/UUIDs; categoricals → profiled value weights; money → moment-matched lognormal (σ² = ln(1+(s/m)²)); counts → floor-matched Poisson; dates → profiled ranges; FKs filled parent-first, zero orphans | **From your profiles** |
| `adp quality-check` | Rules derived from catalog (unique, not-null, range+tolerance, accepted-values, FK) → weighted explained score | From your metadata |
| `adp semantic-model` | Facts vs dims by FK density + measure shape; measures by aggregation heuristics; joins from confirmed FKs → generic or Cube.js YAML | None — structural |
| `adp sql` | Catalog-grounded prompt (PII-safe: no sample values from flagged columns) → provider → SELECT-only guard → hallucinated table names rejected | Your catalog |

## 4. Does it work in any domain? Honest review

### Works out of the box (no customization)

| Capability | Why it's domain-agnostic | Verified |
|---|---|---|
| Catalog / scan / search | information_schema + file inspection | retail (4 tables), any relational shape |
| Profiling & PK/FK inference | pure statistics + naming conventions | 3-level FK chain auto-detected |
| Categorical fidelity | learned from *your* top values, not a template | TVD ≤ 0.006 across 6 columns |
| Numeric fidelity (independent columns) | moment-matched to *your* mean/σ | Δ ≤ 2.1% on all money columns |
| FK-safe volume scaling | parent-first + seeded key pools | 0 orphans at 50k×4 |
| Quality checks & score | derived from metadata, thresholds configurable | 100/100, catches injected orphans |
| Semantic models | structural detection | orders=fact, customers/products=dims |
| MCP / API / CLI / SDK | interface layer is content-blind | 62 tests |

**Conclusion:** for the core use case — *"I have a schema (and ideally sample
data) in domain X, give me realistic FK-safe synthetic data at volume"* — it
works in any domain today with **zero customization**. Healthcare admissions,
bank accounts, factory work orders, and telecom CDRs are all just tables,
keys, categories, quantities, amounts, and dates to this engine.

### Config-only generation (no Python required) — the spec language

`adp apply-spec spec.yaml` covers all of this declaratively, verified across
retail, customer-360, and healthcare domains (see `examples/`):

| Need | Spec syntax |
|---|---|
| Tables, types, PKs | `columns: [{name, type: int/float/string/bool/date/datetime/uuid, primary_key}]` |
| Category mixes | `values: {UPI: 40, Card: 22, …}` (weights, any positive numbers) |
| Numeric shapes | `mean/std/min/max`; money columns auto-lognormal, counts auto-Poisson |
| Date/time ranges | `start:` / `end:` |
| Sparsity | `null_ratio: 0.65` |
| ID/code formats | `format: "ORD-2025-######"` (`#`=digit, `?`=letter) |
| Joins, 3 cardinalities | Cube-style `joins: [{name, relationship: one_to_many/many_to_one/one_to_one, sql}]` — 1:1 gives unique FKs |
| Temporal rules | `after: {column: order_date, min_minutes, max_minutes}` (discharge ≥ admission) |
| Arithmetic rules | `expr: unit_price * quantity - discount_amount` (row-exact) |
| Conditional rules | `null_unless: order_status = 'Returned'`; `CASE WHEN` in expr |
| Hierarchies | `values_by: {column: state, mapping: {Maharashtra: {Mumbai: 55, …}}}` |

### Still requires customization or roadmap

| Gap | Impact | Workaround today | Proper fix (roadmap) |
|---|---|---|---|
| **Cross-table aggregates** — customer.total_spent = Σ their transactions | Declared independently, not summed from children | Post-process with one SQL join | Cross-table derive pass |
| **Statistical correlations** — continuous copulas (salary↔seniority) beyond declared hierarchies/exprs | Marginals faithful; free-form joints not | `values_by` for categorical; `expr` for functional | SDV/copula extra |
| **Time-series autocorrelation** — IoT sensor drift, trends | Rows i.i.d. within declared ranges | Post-process time column | AR/seasonality samplers (platform M4) |
| **Free text** — clinical notes, reviews | `words` placeholder text | LLM post-fill | LLM text sampler with PII guard |
| **Locale value packs** — locale-perfect names/addresses | Shape-valid, generic values | Extend wordlists (§5.1) | Locale plugins |

Rule of thumb: **structure, integrity, distributions, business rules, formats,
and hierarchies → pure config. Cross-table math, free-form correlations,
autocorrelated time-series, and prose → extension or roadmap.**

## 5. Extension points (how to customize)

### 5.1 Add a domain-specific sampler
`generator/samplers.py` — the registry is two lists:

```python
# 1. add the sampler
def _icd10_code() -> Sampler:
    codes = ["E11.9", "I10", "J45.909", "M54.5", "Z00.00"]
    def f(rng, n): return pl.Series([codes[i] for i in rng.choice(len(codes), n)])
    return f

# 2. register: name pattern -> sampler (in _NAME_RULES)
(re.compile(r"(?i)icd|diagnosis_code"), "icd10"),
# 3. map in build_sampler(): case "icd10": return _icd10_code()
```
Note: if the column exists in your source, the profiled `choice` sampler already
reproduces its real code distribution — custom samplers are only for cold-start
or richer semantics.

### 5.2 Add a connector
Subclass `connectors/base.py::Connector`, implement the 6-method contract
(`test_connection, list_schemas, list_tables, get_table_schema, sample_data`,
optional `profile_table` pushdown), register in `connectors/__init__.py::REGISTRY`,
declare a pip extra. Placeholders for Snowflake/Trino/BigQuery show the shape.

### 5.3 Add a quality rule type
`quality/checks.py`: emit it in `derive_rules()` (or store via
`catalog.replace_quality_rules` with `provenance="user_stated"`), implement in
`_run_rule()`, assign a category weight. Thresholds are params, never constants.

### 5.4 Add an LLM provider
Any OpenAI-compatible endpoint is config-only (`base_url` + `api_key_env` in
adp.yaml). A new protocol = one class implementing `complete(system, user)` in
`sql/providers.py` + a registry line.

### 5.5 Add a semantic renderer
`semantic/builder.py::render_semantic_model` — renderers consume the internal
model; add `dbt` etc. without touching detection.

### 5.6 Tune inference thresholds
`PK_UNIQUENESS_THRESHOLD` (0.999), `FK_INCLUSION_THRESHOLD` (0.95),
quality weights (`DEFAULT_WEIGHTS`), range tolerance (0.01) — all module-level
constants intended to become adp.yaml settings; PRs welcome.

## 6. Data & storage layout

```
your-project/
├── adp.yaml           # config: sources (no secrets), provider, generation settings
├── .env               # secrets (gitignored): MINIMAX_API_KEY, PGPASSWORD…
├── .adp/catalog.db    # SQLite metadata catalog (schema_version-ed)
├── data/              # your source files (if file-based)
├── output/            # generated datasets + generated.duckdb
├── model/             # semantic YAML (Cube.js-ready)
└── docs/              # generated data dictionary
```
Catalog logical schema (sources, tables, columns, relationships, profiles,
quality_rules, semantic_models) mirrors the future platform catalog — projects
upgrade losslessly (ADR-0006).

## 7. Security model

Local-first, single-user. Secrets only via env (`${VAR}` interpolation; plaintext
secrets in adp.yaml are rejected at load). Logging masks secret-shaped values.
API/UI bind 127.0.0.1 by default. NL→SQL is read-only (statement classifier +
keyword denylist); PII-flagged columns never contribute sample values to prompts
(ADR-0009 layer-2). All writes constrained to the project root.

## 8. Verified quality gates

62 pytest tests (unit, CLI, API, MCP contract, retail E2E regression) ·
ruff + mypy clean · wheel builds with `twine check` passing · fresh-venv install
smoke · retail validation: 32/32 independent checks (FK, fidelity, privacy,
determinism, analytics) — reports in `examples/retail-ecommerce/`.
