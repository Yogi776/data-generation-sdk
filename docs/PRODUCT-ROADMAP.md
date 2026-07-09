# Product Roadmap

Commercial roadmap for **ai-data-platform (ADP)** — what to sell now, what to build next, and how features map to buyer segments.

> **Positioning:** The fastest way to go from schema to demo-ready, FK-safe data — locally, with quality proof.

---

## Market context

| Market | Size (2025–26) | Growth |
|--------|----------------|--------|
| Synthetic data generation | ~$500M–$950M | ~30–39% CAGR |
| Test data management | ~$1.7B–$2.0B | ~16% CAGR |

**Buyer pain ADP solves:** 2–6 week waits for masked prod exports, broken FK integrity in hand-crafted CSVs, empty BI demos, PII risk in staging environments.

**Competitive set:** Tonic.ai, Mostly AI, Gretel, Snaplet, SDV (open source), Blitz/Syntho (demo data).

**ADP wedge:** Cold-start from `spec.yaml`, local-first, FK-safe generation with quality scoring, auto semantic model, MCP/agent integration, seasonality engine.

See [PRICING.md](./PRICING.md) for tier packaging.

---

## Phase 0 — Sell today (package existing features)

No new engineering required. Monetize what already ships.

| # | Item | Deliverable | Target buyer | Price signal |
|---|------|-------------|--------------|--------------|
| 0.1 | Vertical starter kits | Pre-built `spec.yaml` + research notes + KPI SQL | BI agencies, SIs | $99–$499/kit |
| 0.2 | Demo-in-a-box | Spec → rows → quality report → Cube semantic model | Sales engineers | $199–$999 one-time |
| 0.3 | MCP Agent Pack | Cursor/Claude skills + MCP config + prompts | AI-native dev teams | $29–$99/mo add-on |
| 0.4 | Quality certification report | PDF/HTML with score + FK + seasonality evidence | QA, compliance-light | $49/report |
| 0.5 | Seasonality module | Holiday/peak-season time-series (engine exists) | Retail, e-commerce | Premium add-on |
| 0.6 | Professional services | Spec authoring + 10M row generation + KPI proof | Enterprise POC | $5K–$25K |
| 0.7 | Training workshops | Half-day “synthetic data for BI teams” | Consultancies | $2K–$5K |

**Existing assets to package:**

- Example: `examples/retail-ecommerce/`
- MCP tools: `generate_synthetic_data`, `run_quality_check`, `create_semantic_model`, `validate_business_questions`
- Benchmarks: 10M rows/table, 171K rows/s, 100/100 quality score

---

## Phase 1 — Build fast, sell fast (1–3 months)

| # | Feature | Why customers pay | Effort | Tier |
|---|---------|-------------------|--------|------|
| 1.1 | **Hosted cloud runner** | No local install; shareable dataset links | M | Team+ |
| 1.2 | **Spec template marketplace** | Browse/download domain specs | S | Starter+ |
| 1.3 | **One-click warehouse export** | Push to Snowflake / BigQuery / Postgres / Databricks | M | Team+ |
| 1.4 | **Cube / dbt export pack** | Semantic model + dbt models + metrics | S | Team+ |
| 1.5 | **CI/CD GitHub Action** | `apply-spec` → `generate` → `quality-check` on PR | S | Team+ |
| 1.6 | **Generation REST API** | `POST /generate?seed=42&rows=1M` for pipelines | M | Business+ |
| 1.7 | **Multi-project workspace** | Manage 10+ client specs (consultancies) | M | Team+ |
| 1.8 | **Polished web UI** | Upload schema → generate → download (non-technical users) | L | Team+ |
| 1.9 | **Run comparison** | Diff quality scores + KPI drift between spec versions | S | Team+ |
| 1.10 | **Edge-case generator** | Fraud cases, zero-balance accounts, expired policies | M | Business+ |
| 1.11 | **Locale packs** | India, EU, US names, phones, currencies | S | Add-on |

**Effort key:** S = small (1–2 weeks), M = medium (3–6 weeks), L = large (6+ weeks)

---

## Phase 2 — Core paid platform (3–6 months)

Unlocks **$2K–$15K/year** mid-market deals.

| # | Feature | Competes with | Tier |
|---|---------|---------------|------|
| 2.1 | Production DB sync | Tonic.ai | Business |
| 2.2 | Mask + synthesize hybrid | Delphix, Tonic | Business |
| 2.3 | Scheduled refresh | Enterprise QA | Business |
| 2.4 | Team data catalog | Collibra-lite | Business |
| 2.5 | RBAC (admin / generator / viewer) | Table stakes | Business |
| 2.6 | Audit log | Compliance buyers | Business |
| 2.7 | SSO (SAML/OIDC) | Enterprise procurement | Enterprise |
| 2.8 | API keys + rate limits | Gretel | Business |
| 2.9 | Webhooks (Slack/Teams) | DevOps | Team+ |
| 2.10 | Custom sampler SDK | Platform play | Enterprise |
| 2.11 | Distribution calibration UI | Mostly AI | Business |
| 2.12 | Privacy report (PII scan on output) | Compliance-light | Business |
| 2.13 | DuckDB quality-check support | Gap today | Team+ |

---

## Phase 3 — Enterprise & regulated (6–12 months)

Unlocks **$15K–$75K+/year**. Requires legal/compliance investment.

| # | Feature | Buyer |
|---|---------|-------|
| 3.1 | Differential privacy mode | BFSI, healthcare |
| 3.2 | Synthetic data certificate (utility + privacy score) | Regulated enterprise |
| 3.3 | HIPAA / GDPR compliance pack (BAA, DPA, residency) | Healthcare, EU |
| 3.4 | On-prem / air-gapped license | Banks, government |
| 3.5 | VPC / private cloud (Helm on customer AWS/GCP) | Enterprise |
| 3.6 | Multi-tenant SaaS | Large orgs |
| 3.7 | Advanced lineage (spec → sampler → output → metric) | Data governance |
| 3.8 | Re-identification risk scoring | Legal/compliance |
| 3.9 | SOC 2 Type II | Enterprise procurement |

---

## Phase 4 — AI-native differentiators (ongoing)

Hard for incumbents to copy; strong Cursor/agent ecosystem fit.

| # | Feature | Status |
|---|---------|--------|
| 4.1 | Natural language → spec | Skill exists; needs productized UI |
| 4.2 | Agent orchestration studio | Workflow in `agent/`; needs visual layer |
| 4.3 | Auto domain research | `adp-domain-research` skill exists |
| 4.4 | NL business Q&A + insights | `generate_business_insights` MCP tool exists |
| 4.5 | Spec from ERD/diagram | New |
| 4.6 | Spec from sample CSV (confidence scores) | `profile` exists; needs UX |
| 4.7 | Auto-fix failing quality checks | Calibrate skill exists |
| 4.8 | Cursor/Claude Desktop plugin | MCP config templates exist |
| 4.9 | Benchmark-as-a-service | `benchmarks/bench_generation.py` exists |

---

## Vertical SKUs (named products)

Package the same engine as industry-specific products for clearer GTM.

| SKU | Tables / features | Target | Price signal |
|-----|-------------------|--------|--------------|
| **ADP for Retail** | Orders, payments, shipments, seasonality, fraud edge cases | E-commerce, POS | $299/mo |
| **ADP for Healthcare** | Claims, patients, providers, HIPAA report | Health tech | $499/mo |
| **ADP for BFSI** | Accounts, transactions, fraud scenarios | Fintech | $499/mo |
| **ADP for SaaS** | Users, subscriptions, events, churn | B2B SaaS | $199/mo |
| **ADP for Sales Demos** | Prospect KPIs + BI export + talk track | Sales engineers | $99–$299/mo |
| **ADP for QA** | CI plugin + refresh + FK guarantee | QA leads | $199/mo |
| **ADP for ML** | Distribution-preserving augmentation | ML engineers | $299/mo |

---

## Partner & services revenue

| # | Offering | Revenue model |
|---|----------|---------------|
| P.1 | White-label for system integrators | $5K–$20K/yr license |
| P.2 | Certified implementer program | $500–$2K/certification |
| P.3 | Custom domain build (2-week engagement) | $10K–$50K |
| P.4 | Managed demo environments (monthly refresh) | $500–$2K/mo/client |
| P.5 | Migration from Faker/SDV scripts | $3K–$10K |
| P.6 | BI vendor OEM (Cube, Looker, ThoughtSpot) | Revenue share |

---

## Target customers (priority order)

### Tier 1 — Best fit now

| Segment | Buyer title | Entry offer |
|---------|-------------|-------------|
| System integrators & BI consultancies | Solutions architect | Vertical kits + white-label |
| Sales engineers | Sales engineer, SE | Demo-in-a-box |
| BI / analytics agencies | Analytics engineer | Semantic model + KPI pack |
| Data engineers (mid-market SaaS) | Data engineer | CLI + CI plugin |
| AI agent / Cursor users | Developer | MCP Agent Pack |

### Tier 2 — After Phase 1–2

| Segment | Entry offer |
|---------|-------------|
| QA / test engineering | ADP for QA SKU |
| ML engineers | ADP for ML SKU |
| Startups pre-Series B | Team cloud tier |

### Tier 3 — After Phase 3

| Segment | Entry offer |
|---------|-------------|
| BFSI / insurance | Enterprise + privacy certificate |
| Healthcare / pharma | ADP for Healthcare + HIPAA pack |
| Large enterprise DevOps | DB sync + on-prem |

---

## Top 10 build priorities (90-day focus)

| Priority | Item | Phase |
|----------|------|-------|
| 1 | Hosted cloud runner | 1.1 |
| 2 | Vertical starter kits (retail, healthcare, SaaS) | 0.1 |
| 3 | CI/CD GitHub Action | 1.5 |
| 4 | One-click Postgres/Snowflake export | 1.3 |
| 5 | Spec template marketplace | 1.2 |
| 6 | Multi-project workspace | 1.7 |
| 7 | Production DB sync | 2.1 |
| 8 | Natural language → spec (productized) | 4.1 |
| 9 | Distribution calibration UI | 2.11 |
| 10 | White-label SI program | P.1 |

---

## Defer (avoid for now)

| Item | Why |
|------|-----|
| Full HIPAA certification | 6–12 months, high legal cost |
| Image/video synthetic data | Different market; Gretel owns modality |
| Row-level pricing race | SDV is free; compete on workflow + quality proof |
| Generic “AI platform” positioning | Sell **demo data** or **test data** specifically |

---

## Success metrics

| Metric | 90-day target | 12-month target |
|--------|---------------|-----------------|
| Paying teams | 10 | 100 |
| Vertical kits sold | 50 | 500 |
| SI partners | 3 | 15 |
| MRR | $5K | $50K |
| NPS (paid users) | ≥ 40 | ≥ 50 |
| Quality score on generated data | ≥ 95 | ≥ 98 |
| Time to first dataset (new user) | < 10 min | < 5 min |

---

## Related docs

- [PRICING.md](./PRICING.md) — tier packaging and add-ons
- [USE-CASES.md](./USE-CASES.md) — persona workflows
- [GETTING-STARTED.md](./GETTING-STARTED.md) — technical onboarding
- [MCP-GUIDE.md](./MCP-GUIDE.md) — agent integration
