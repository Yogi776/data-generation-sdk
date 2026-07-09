# Pricing

One-page pricing draft for **ai-data-platform (ADP)**.  
Open-source core stays free (Apache-2.0). Paid tiers add cloud, collaboration, integrations, and support.

> **Draft only** — prices and limits are starting points for design partners and early customers.

---

## Plans at a glance

| | **Community** | **Starter** | **Team** | **Business** | **Enterprise** |
|---|:---:|:---:|:---:|:---:|:---:|
| **Price** | Free | $49/mo | $199/mo | $999/mo | Custom |
| **Billed annually** | — | $39/mo | $159/mo | $799/mo | $15K+/yr |
| **Best for** | Individual devs | Freelancers, POCs | Small data/BI teams | Mid-market SaaS | Regulated / large orgs |

---

## Community — Free

Everything you need to evaluate and build locally.

- CLI + Python SDK
- Unlimited local generation
- `spec.yaml` cold-start generation
- FK-safe output (Parquet, CSV, DuckDB)
- Quality check + seasonality check
- Semantic model (Cube.js YAML)
- MCP server + agent skills
- Apache-2.0 license

**Limits:** Local machine only. No team features. Community support (GitHub Issues).

```bash
pip install ai-data-platform
adp init && adp apply-spec spec.yaml && adp generate-data
```

---

## Starter — $49/month

For freelancers and solo builders who want templates and light cloud usage.

| Included | Limit |
|----------|-------|
| Cloud generation | 1M rows/month |
| Vertical starter kits | 1 domain (retail, healthcare, or SaaS) |
| Quality certification PDF | 5/month |
| Spec template marketplace | Browse + 3 downloads/month |
| Email support | 48h response |

**Add-ons:**

| Add-on | Price |
|--------|-------|
| Extra 1M cloud rows | $10 |
| Additional vertical kit | $99 one-time |
| Locale pack (US, EU, India) | $29 one-time |

---

## Team — $199/month

For BI agencies, consultancies, and data teams shipping demos and test data.

Everything in **Starter**, plus:

| Included | Limit |
|----------|-------|
| Cloud generation | 10M rows/month |
| Multi-project workspace | 10 projects |
| MCP Agent Pack | Included |
| CI/CD GitHub Action | 3 repos |
| Cube / dbt export pack | Included |
| Warehouse export | Postgres, DuckDB |
| All vertical starter kits | 3 domains |
| Run comparison (spec diff) | Included |
| Webhooks (Slack) | Included |
| Email support | 24h response |

**Add-ons:**

| Add-on | Price |
|--------|-------|
| Extra 10M cloud rows | $75 |
| Additional CI repo | $29/mo |
| Snowflake / BigQuery export | $99/mo |
| ADP for Sales Demos SKU | $99/mo |

---

## Business — $999/month

For mid-market companies replacing masked prod exports and manual test data.

Everything in **Team**, plus:

| Included | Limit |
|----------|-------|
| Cloud generation | 100M rows/month |
| Production DB sync | 2 connections |
| Scheduled refresh | Daily |
| Distribution calibration | Included |
| RBAC (admin / generator / viewer) | 25 seats |
| Audit log | 90-day retention |
| API keys + REST API | 5 keys |
| Privacy report (PII scan) | Included |
| SSO | — |
| Priority support | 4h response, Slack channel |

**Add-ons:**

| Add-on | Price |
|--------|-------|
| Extra DB connection | $199/mo |
| Extra 50M rows | $299 |
| SSO (SAML/OIDC) | $199/mo |
| On-demand edge-case packs | $99/mo |

---

## Enterprise — Custom ($15,000+/year)

For regulated industries and large organizations.

Everything in **Business**, plus:

| Included | Notes |
|----------|-------|
| Unlimited cloud rows | Or dedicated capacity |
| SSO + SCIM | Included |
| On-prem / air-gapped license | Optional |
| VPC / private cloud deploy | Helm on your AWS/GCP |
| Differential privacy mode | Roadmap |
| Synthetic data certificate | Roadmap |
| HIPAA / GDPR compliance pack | Roadmap |
| Custom samplers | Engineering engagement |
| Dedicated success engineer | Quarterly reviews |
| SLA | 99.9% API availability |

**Contact:** [yogesh.khangode@tmdc.io](mailto:yogesh.khangode@tmdc.io)

---

## Vertical SKUs (add to any paid plan)

Industry-specific packages — same engine, pre-configured specs and KPIs.

| SKU | What's included | Monthly add-on |
|-----|-----------------|--------------|
| **ADP for Retail** | Orders, payments, shipments, seasonality, fraud scenarios | $99/mo |
| **ADP for Healthcare** | Claims, patients, providers, compliance report | $149/mo |
| **ADP for BFSI** | Accounts, transactions, fraud edge cases | $149/mo |
| **ADP for SaaS** | Users, subscriptions, events, churn patterns | $79/mo |
| **ADP for Sales Demos** | Prospect KPIs, BI export, demo talk track | $99/mo |
| **ADP for QA** | CI plugin, refresh automation, FK guarantee | $99/mo |
| **ADP for ML** | Distribution-preserving augmentation, bias balance | $129/mo |

---

## One-time products

| Product | Price | Deliverable |
|---------|-------|-------------|
| **Demo-in-a-box** | $499 | Spec + 500K rows + quality report + semantic model + sample queries |
| **Vertical starter kit** | $199 | Spec YAML + research notes + KPI SQL + validation scripts |
| **Quality certification report** | $49 | PDF with score, FK checks, seasonality evidence |
| **Benchmark audit** | $499 | Performance report for your spec at 1M–10M scale |
| **Migration package** | $2,999+ | Replace Faker/SDV scripts with ADP specs |

---

## Professional services

| Engagement | Duration | Price range |
|------------|----------|-------------|
| Spec authoring workshop | 1 day | $2,000–$5,000 |
| Custom domain build | 2 weeks | $10,000–$25,000 |
| Managed demo environment | Ongoing | $500–$2,000/mo |
| White-label SI license | Annual | $5,000–$20,000/yr |
| Certified implementer training | 2 days | $1,500/seat |

---

## Usage-based API pricing (Business+)

For programmatic generation outside included quotas:

| Volume | Price per 100K rows |
|--------|---------------------|
| First 10M/mo (Team) | Included |
| 10M–100M/mo (Business) | Included |
| Over quota | $0.50 |
| Enterprise volume | Custom ($0.10–$0.30) |

Generation is deterministic with `--seed` — same spec + seed = same data (CI-friendly).

---

## Compare to alternatives

| | ADP Team | Gretel Team | Tonic.ai | Snaplet |
|---|:---:|:---:|:---:|:---:|
| Monthly price | $199 | $295 | Custom ($1K+/mo) | $0–$200 |
| Local-first | ✓ | — | — | — |
| Spec cold-start (no sample) | ✓ | — | — | — |
| FK-safe + quality score | ✓ | Partial | ✓ | ✓ |
| Semantic model export | ✓ | — | — | — |
| MCP / agent native | ✓ | API | — | — |
| Production DB sync | Business+ | — | ✓ | Postgres only |
| Formal privacy cert | Enterprise | ✓ | Partial | — |

---

## FAQ

**Is the open-source version going away?**  
No. Community (CLI, local generation, MCP, quality checks) stays free under Apache-2.0 forever.

**Can I self-host everything on Team?**  
Yes. Team cloud is optional. Run locally with unlimited rows; pay for collaboration, templates, and integrations.

**Do you offer discounts for startups or education?**  
Yes — 50% off Starter and Team for qualifying startups (<$2M raised) and academic use. Contact us.

**What counts as a “row”?**  
Total rows written across all tables in a generation run. 10M `fact_orders` + 10M `fact_payments` = 20M rows.

**Is generated data GDPR/HIPAA safe?**  
Community and Team tiers generate synthetic data with no real PII. Enterprise tier adds formal privacy reports and compliance packs (roadmap).

---

## Get started

1. **Try free:** `pip install ai-data-platform` → [GETTING-STARTED.md](./GETTING-STARTED.md)
2. **Book a demo:** Design partner program — first 10 Team customers get 3 months at 50% off
3. **Enterprise:** Email [yogesh.khangode@tmdc.io](mailto:yogesh.khangode@tmdc.io)

---

## Related

- [PRODUCT-ROADMAP.md](./PRODUCT-ROADMAP.md) — feature phases and build priorities
- [USE-CASES.md](./USE-CASES.md) — workflows by persona
