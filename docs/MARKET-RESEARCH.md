# Market Research Summary

Why people buy synthetic data platforms, where **ai-data-platform (ADP)** fits, who to target, and how to earn revenue.

> Research compiled July 2026 from industry reports, competitor case studies, and buyer guides.

---

## 1. Why people purchase synthetic data platforms

This is not a "nice to have" category. Buyers pay because the alternative is slow, risky, and expensive.

### The 5 core purchase drivers

| Driver | What buyers feel today | What they pay for | Market evidence |
|--------|------------------------|-------------------|-----------------|
| **Speed** | 2–6 weeks waiting for masked prod exports; 3–5 day DB refresh cycles | Instant datasets for dev, QA, demos | 30–60% faster dev cycles; 93% faster deployments vs masked prod |
| **Compliance / risk** | GDPR, HIPAA, CCPA fines; PII in staging | Zero-PII synthetic data | Avg GDPR fine ~€20M; firms spend $3M+/yr on data protection |
| **Cost** | Manual labeling, storage, data engineering time | Automated generation at scale | 70% lower data acquisition cost; 80% of data scientist time on prep |
| **Quality** | Hand-crafted CSVs break FKs; fake data misses edge cases | FK-safe, statistically realistic, scored data | eBay: referential subsets improved test pass rates; Patterson: 75% less test data prep |
| **AI readiness** | No data for new products; can't train without prod access | Training sets, sandboxes, agent test data | Gartner: 60% of AI training data synthetic by 2026; Nvidia acquired Gretel (~$320M) |

### The CFO pitch

Buyers don't buy "synthetic data." They buy:

1. **Faster time-to-market** — ship demos and features weeks earlier
2. **Lower compliance risk** — no prod data in dev/staging
3. **Higher test coverage** — edge cases, scale, FK integrity
4. **Unblocked AI projects** — train and test without legal review loops

**Typical ROI:** 12–18 months. Many teams see payback on the first 1–2 projects.

### Market size

| Market | 2025–26 size | Growth |
|--------|--------------|--------|
| Synthetic data generation | ~$500M–$950M | ~30–39% CAGR |
| Test data management | ~$1.7B–$2.0B | ~16% CAGR |

---

## 2. Where ADP should position

### Market gap

The market splits into two viable positions:

```
ENTERPRISE TIER                    ACCESSIBLE LAYER
(Nvidia/Gretel, Tonic, Mostly AI)  (underserved)
─────────────────────────────────  ─────────────────────────────
$15K–$200K/yr                      $0–$299/mo
DB sync, masking, privacy certs    Spec → data in minutes
Sales-led, 6–12 month sales cycle  Self-serve, dev/agent-led
Needs prod data sample             Cold-start from schema/intent
```

### ADP positioning statement

> **The accessible, local-first synthetic data platform — from schema to demo-ready, FK-safe data with quality proof, in minutes. Built for data engineers, BI teams, and AI agents — not just Fortune 500 compliance teams.**

**One-liner:** Spec to stakeholder demo — FK-safe data, quality score, and BI-ready semantic model in one session. Local. Open source. Agent-native.

### Competitive positioning

| Competitor | Their wedge | ADP counter |
|------------|-------------|-----------|
| **Tonic.ai** | Prod DB → de-identified test data | No prod data needed — start from `spec.yaml` |
| **Mostly AI** | Statistical fidelity from real data | Cold-start + calibration for greenfield POCs |
| **Gretel** | Privacy SDK, ML training | Workflow + quality score + semantic layer |
| **Snaplet** | Postgres dev seeding | Any domain, any format, agent-native |
| **Faker / SDV** | Free DIY | FK-safe, scored, semantic model, seasonality |
| **MockHero / Unicourn** | API, plain English | Local, open source, quality proof, Cube export |
| **Blitz** | Sales demo narratives | Self-serve + SI-ready, not sales-only |

---

## 3. Use cases (ranked by ADP fit)

| # | Use case | Who feels pain | ADP fit |
|---|----------|----------------|---------|
| 1 | Pre-sales demo data | Sales engineers, solution architects | ★★★★★ |
| 2 | QA / CI test data | QA leads, DevOps | ★★★★★ |
| 3 | Analytics sandbox | BI developers, data analysts | ★★★★★ |
| 4 | Greenfield product POC | Product, ML teams | ★★★★★ |
| 5 | Onboarding new engineers | Engineering managers | ★★★★☆ |
| 6 | ML training augmentation | ML engineers | ★★★★☆ |
| 7 | Load / performance testing | Platform engineers | ★★★★☆ |
| 8 | Partner / vendor data sharing | Legal, compliance | ★★★☆☆ |
| 9 | Regulated prod-data replacement | BFSI, healthcare | ★★☆☆☆ (needs certs) |

### Highest-conversion use cases for ADP today

1. **"I need a demo by Friday"** — BI consultancies, sales engineers
2. **"Our test data is broken"** — mid-market SaaS QA teams
3. **"We're building before prod exists"** — startups, new product lines
4. **"Our AI agent needs data in the IDE"** — Cursor/Claude power users

---

## 4. Customer segments

### Buyer personas

| Persona | Title | Role in deal |
|---------|-------|--------------|
| **Champion** | Data engineer, analytics engineer | Influencer — cares about speed, FK integrity, CLI |
| **Economic buyer** | VP Engineering, CTO | Approver ($5K–$50K) — cares about ROI, risk |
| **User** | BI developer, QA engineer, sales engineer | Daily user — realistic KPIs, easy refresh |
| **Blocker** | Security, legal, compliance | Gatekeeper — no PII, audit trail |
| **Procurement** | IT procurement | Contract — SSO, SLA |

**Decision unit:** Usually 3–5 people (Engineering + Security + Procurement).

### Tier 1 — Target now (0–6 months)

| Segment | Company profile | Why they buy | Entry offer |
|---------|-----------------|--------------|-------------|
| BI / analytics consultancies | 20–500 people | Every client needs demo data | White-label + vertical kits |
| Sales engineers at BI vendors | ThoughtSpot, Looker, Power BI partners | Prospect-specific demos | ADP for Sales Demos SKU |
| Mid-market SaaS | 50–500 employees | Test data blocks releases | Team plan + CI plugin |
| Data engineering agencies | dbt/Cube implementers | Client onboarding friction | Partner program |
| AI-native startups | Agent builders | Structured test data | MCP pack + API |
| System integrators | Regional SIs | Repeatable client setups | Services + license |

### Tier 2 — After product maturity (6–12 months)

Fintech, health tech, e-commerce tech, enterprise QA orgs. Requires DB sync, SSO, compliance features.

### Tier 3 — Long-term (12–24 months)

Large banks (Erste Group, Citi), healthcare systems, marketplaces (eBay). Requires formal privacy certification and enterprise sales motion.

---

## 5. Companies & ecosystems to target

### Consulting & SI partners

| Type | Examples | Why partner |
|------|----------|-------------|
| dbt consulting partners | Analytics8, Aimpoint Digital, phData | Every dbt project needs seed data |
| Cube partners | Cube.dev implementers | ADP auto-generates Cube semantic models |
| BI consultancies | Slalom, Capgemini data practice, boutiques | Demo environments per client |
| India analytics firms | AnalytixLabs, local BI shops | Training + demo data demand |

### Technology partners

| Partner | Integration | Co-sell angle |
|---------|-------------|---------------|
| Cube.dev | Semantic model export | Generate data + metrics layer together |
| dbt Labs | dbt models from generated data | Seed your dbt project day one |
| DuckDB | Native output format | Local analytics without warehouse |
| Snowflake / Databricks | One-click export | Demo data in customer warehouse |
| Cursor | MCP server | Agent generates your test data |
| GitHub | CI Action | Quality-gated test data on every PR |
| ThoughtSpot / Looker | Demo data for partners | Prospect-specific liveboards |

### Competitor customers (alternative positioning)

Companies using Tonic, Mostly AI, or Gretel for enterprise use — potential ADP targets for **demo/sandbox** use cases:

- **Tonic:** eBay, Everlywell, Patterson Dental, Pax8, Wellthy
- **Mostly AI:** Erste Group, Citi, Telefonica
- **Gretel:** Illumina, healthcare institutions

**ADP angle:** "You don't need $100K Tonic for a sales demo — ADP does spec → data → KPIs in 10 minutes, locally."

---

## 6. How to earn money

### Revenue model

```
FREE (open source)  →  SELF-SERVE ($49–299/mo)  →  TEAM ($199–999/mo)  →  ENTERPRISE ($15K+/yr)
     │                        │                          │                        │
  Adoption              Templates, cloud           DB sync, SSO            On-prem, compliance
  Community             MCP pack, CI               API, calibration        White-label, services
```

### 7 revenue streams (ranked by near-term feasibility)

| # | Stream | Price range | Timeline |
|---|--------|-------------|----------|
| 1 | Professional services | $5K–$25K/project | Now |
| 2 | Vertical starter kits | $99–$499/kit | Now |
| 3 | Team SaaS subscription | $49–$199/mo | 1–3 months |
| 4 | Demo-in-a-box | $199–$999 one-time | Now |
| 5 | SI white-label license | $5K–$20K/yr | Now |
| 6 | Usage-based API | $0.10–$0.50/100K rows | 3 months |
| 7 | Enterprise contracts | $15K–$75K/yr | 6–12 months |

### Conservative 12-month revenue scenario

| Stream | Units | Revenue |
|--------|-------|---------|
| 10 Team @ $199/mo | 10 | $24K/yr |
| 5 services @ $10K | 5 | $50K |
| 50 vertical kits @ $199 | 50 | $10K |
| 3 SI partners @ $10K/yr | 3 | $30K |
| 2 Business @ $999/mo | 2 | $24K/yr |
| **Total Year 1** | | **~$114K–$140K** |

With one enterprise deal ($25K+) or 50 Team customers → **$250K+ ARR** in 18 months.

See [PRICING.md](./PRICING.md) for tier details.

---

## 7. Who can help grow ADP

### Roles to hire or partner with

| Role | What they do |
|------|--------------|
| Founding engineer | Cloud, API, CI plugin |
| Developer advocate | Content, demos, community (dbt/Cube/Cursor) |
| Solutions consultant | Client specs, services delivery |
| Partnerships lead | Cube, dbt, Cursor co-sell |
| Compliance advisor | GDPR/HIPAA roadmap (fractional) |

### Partner types

| Partner | How they help | What you give |
|---------|---------------|---------------|
| BI consultancies | 5–20 clients/year | White-label, rev share |
| dbt/Cube implementers | Embed in every project | Certification program |
| BI vendor SE teams | Use for every demo | Sales Demos SKU |
| Bootcamps / trainers | Teach with ADP datasets | Free education tier |
| OSS contributors | Samplers, locale packs | Bounties, recognition |
| Cursor / MCP ecosystem | Distribution to agent users | Native integration |

### Communities for distribution

- dbt Slack / meetups
- Cube Discord
- r/dataengineering, r/BusinessIntelligence
- Data Twitter/X
- Cursor forum / Discord
- GitHub (OSS stars → credibility)

---

## 8. Competitive lessons

### What works

| Pattern | Example |
|---------|---------|
| Workflow integration beats raw generation | Tonic in CI/CD; Gretel in ML pipelines |
| Land with devs, expand to enterprise | Gretel free → Team → Enterprise |
| Vertical beats horizontal | MDClone (healthcare), Blitz (sales demos) |
| Accessible layer is underserved | MockHero, Unicourn, SynthForge emerging |
| Agent-native is new | MockHero MCP; ADP already has this |

### What kills startups

| Failure mode | ADP response |
|--------------|--------------|
| Single-function "just generate data" | Bundle spec + generate + quality + semantic + analytics |
| No workflow integration | CI plugin, MCP, warehouse export |
| Competing with hyperscalers on enterprise | Start accessible; move upmarket later |
| Tabular commoditization | Differentiate on cold-start, quality proof, semantic layer, agents |

---

## 9. 90-day GTM playbook

### Month 1 — Prove & package
- Ship 3 vertical kits (retail, healthcare, SaaS)
- Record demo videos: "spec → demo in 10 min"
- Publish benchmark + quality score as sales proof
- Launch design partner program (10 teams, 50% off)

### Month 2 — Distribute
- Post in dbt/Cube/Cursor communities
- Reach 5 BI consultancies for partner conversations
- GitHub README + Product Hunt launch

### Month 3 — Monetize
- Launch Team tier (hosted runner or templates)
- Close 2–3 services engagements ($5K–$10K each)
- Sign 1 SI white-label partner

---

## 10. Executive summary

| Question | Answer |
|----------|--------|
| Why do people buy? | Speed, compliance, quality, cost, AI readiness |
| Is the need real? | Yes — $500M–$2B market, 30%+ CAGR |
| Where does ADP fit? | Accessible layer — spec → demo-ready with quality proof |
| Best customers now? | BI consultancies, sales engineers, mid-market SaaS QA, AI agent devs |
| Best use cases now? | Sales demos, QA/CI test data, analytics sandboxes, greenfield POCs |
| How to earn? | Services now → Team SaaS → SI white-label → Enterprise later |
| Year 1 realistic revenue? | $100K–$150K; $250K+ with enterprise or scale |

---

## Related docs

- [PRICING.md](./PRICING.md) — tier packaging and add-ons
- [PRODUCT-ROADMAP.md](./PRODUCT-ROADMAP.md) — feature phases and build priorities
- [OUTBOUND-TEMPLATES.md](./OUTBOUND-TEMPLATES.md) — email templates for first customers
- [USE-CASES.md](./USE-CASES.md) — persona workflows
