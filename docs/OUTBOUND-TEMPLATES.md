# Outbound Email Templates

Ready-to-send templates for ADP's first three target segments. Customize `[brackets]` before sending.

**Design partner offer:** First 10 teams get 50% off Team plan for 3 months + free vertical starter kit.

---

## Template 1 — BI / Analytics Consultancies

**Target:** Founder, practice lead, or senior analytics consultant at a 20–500 person BI shop.

**Subject options:**
- `Cut client demo setup from days to 10 minutes?`
- `FK-safe demo data for your next [Looker/Cube/Power BI] engagement`
- `Partner idea: synthetic data for every client kickoff`

---

**Email:**

Hi [First name],

I noticed [Company] delivers [Looker/Cube/dbt/Power BI] implementations for clients in [retail/healthcare/SaaS/etc.].

Quick question: how long does your team spend building realistic demo datasets before a client workshop or POC?

Most consultancies we talk to lose **2–5 days per engagement** hand-crafting CSVs or waiting on the client's prod data access. The data often breaks FK relationships or looks fake in dashboards.

We built **ai-data-platform (ADP)** — an open-source tool that turns a schema (`spec.yaml`) into:

- FK-safe synthetic data (Parquet/CSV/DuckDB) in minutes
- Automated quality score (100/100 with evidence)
- Auto-generated Cube.js semantic model for BI
- Realistic KPIs (revenue by city, seasonality, etc.)

**Example flow:** `apply-spec` → `generate-data` → `quality-check` → `semantic-model` → demo-ready in one session. No production data. Runs locally.

We're looking for **3 design partner consultancies** to:

1. Use ADP on a live client engagement (we help with the spec)
2. Give feedback on vertical templates (retail, healthcare, SaaS)
3. Get **50% off Team plan for 3 months** + a free starter kit

Would a 20-minute call next week make sense? I can walk through a retail demo generating 50K rows with full FK integrity and a working semantic layer.

Best,
[Your name]
[Title] | ai-data-platform
[GitHub link] | [Calendar link]

**P.S.** Benchmark: 10M rows/table in ~3 minutes, 171K rows/s, quality score 100/100 on our seasonal-retail example.

---

## Template 2 — Sales Engineers (BI / Analytics Vendors)

**Target:** Sales engineer, solutions architect, or pre-sales lead at a BI/analytics vendor or their implementation partner.

**Subject options:**
- `Prospect-specific demo data in 10 minutes (no prod access)`
- `ThoughtSpot/Looker demo with realistic KPIs — without Blitz pricing`
- `Your next demo: FK-safe data + semantic layer, locally`

---

**Email:**

Hi [First name],

When you prep a demo for [prospect company] in [industry], how do you handle the data layer?

The usual options aren't great:
- **Empty dashboards** — kills credibility in the first 5 minutes
- **Canned demo data** — doesn't match the prospect's industry or KPIs
- **Prod/sample exports** — security review, PII risk, weeks of delay
- **Blitz / custom builds** — great output, but another vendor and budget line

**ai-data-platform** is built for exactly this:

```
spec.yaml (industry + tables + KPIs)
    → generate 50K–500K rows (FK-safe, seasonality-aware)
    → quality score 100/100
    → Cube semantic model
    → push to Snowflake / Postgres / DuckDB / CSV
```

**No production data. Runs on your laptop. Agent-native** (works in Cursor via MCP).

For a retail prospect: orders, payments, shipments with Diwali/holiday seasonality — demo-ready in **under 15 minutes**.

I'd love to show you a live run on a prospect-like scenario. We're offering the first 10 sales engineering teams:

- Free **ADP for Sales Demos** starter kit
- Co-build one prospect-specific spec together
- 50% off Team plan for 3 months

Open to a quick screen share this week?

[Your name]
[Calendar link] | [2-min demo video link if you have one]

---

## Template 3 — Mid-Market SaaS QA / Engineering Leads

**Target:** Director of QA, VP Engineering, or platform/DevOps lead at a 50–500 person B2B SaaS company.

**Subject options:**
- `Stop waiting 3 weeks for masked prod exports`
- `FK-safe test data for CI — seed=42, quality score included`
- `Your staging DB shouldn't need a Jira ticket`

---

**Email:**

Hi [First name],

Does your QA or platform team ever hit this loop?

1. File Jira ticket for staging data
2. Wait 3–14 days for data engineering
3. Get a prod export that's 6 weeks stale
4. Tests fail on schema drift or missing edge cases
5. Compliance still nervous about PII in staging

Teams using **Tonic** or manual masking solve this — but it's often **$15K–$100K/year** and still requires production data access.

We built **ai-data-platform (ADP)** as an open-source alternative for the **generate-from-spec** path:

| | Manual CSVs | Masked prod | ADP |
|---|:---:|:---:|:---:|
| FK integrity | ✗ | ✓ | ✓ |
| No prod data needed | ✓ | ✗ | ✓ |
| Deterministic (CI seed) | ✗ | Partial | ✓ (seed=42) |
| Quality score | ✗ | ✗ | ✓ (0–100) |
| Setup time | Days | Weeks | Minutes |

```bash
adp apply-spec spec.yaml
adp generate-data --rows 100000 --seed 42
adp quality-check   # → 100/100, 0 orphans
```

**Benchmark:** 10M rows across 3 tables in ~3 minutes. Runs locally — nothing leaves your network.

We're recruiting **3 SaaS teams** as design partners to:

- Replace one broken test data workflow with ADP
- Get a custom spec for your schema (we help)
- **50% off Team plan** + CI integration roadmap input

Worth 20 minutes to see if this fits [Company]'s staging/CI setup?

[Your name]
[GitHub] | [Calendar link]

**P.S.** Apache-2.0 — your team can POC free today: `pip install ai-data-platform`

---

## Follow-up sequence (all segments)

### Follow-up 1 — Day 4 (if no reply)

**Subject:** `Re: [original subject]`

Hi [First name],

Bumping this in case it got buried.

Happy to send a **2-minute Loom** instead of a call — I'll generate 50K rows of retail data with FK integrity and a quality report, start to finish.

Worth a look?

[Your name]

---

### Follow-up 2 — Day 10 (if no reply)

**Subject:** `Free retail demo kit — no call needed`

Hi [First name],

No worries if timing's off. Sharing our **seasonal-retail starter kit** anyway — spec + 100K row generation + quality checks:

[Link to examples/seasonal-retail/]

If test/demo data becomes a priority later, we're here.

[Your name]

---

## Personalization checklist

Before sending, customize:

- [ ] `[Company]` — their name and what they do
- [ ] `[Industry]` — retail, healthcare, fintech, SaaS
- [ ] `[BI tool]` — Looker, ThoughtSpot, Power BI, Cube, dbt
- [ ] Specific pain from LinkedIn post, job listing, or case study
- [ ] One proof point: benchmark, quality score, or example link

## Where to find leads

| Segment | Sources |
|---------|---------|
| BI consultancies | dbt partner directory, Cube community, LinkedIn "analytics consultant" |
| Sales engineers | ThoughtSpot/Looker partner pages, BI vendor LinkedIn |
| SaaS QA leads | LinkedIn "Director of QA" + 50–500 employees, r/QualityAssurance |

---

## Related docs

- [MARKET-RESEARCH.md](./MARKET-RESEARCH.md) — full market analysis and target segments
- [PRICING.md](./PRICING.md) — design partner pricing
- [PRODUCT-ROADMAP.md](./PRODUCT-ROADMAP.md) — what to offer partners
