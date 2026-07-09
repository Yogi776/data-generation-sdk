# Data Marketplace Research

Can ADP sell synthetic data directly? Feasibility, models, pricing, legal requirements, and launch plan.

> Research compiled July 2026.

---

## Executive summary

| Question | Answer |
|----------|--------|
| Can you create a data marketplace? | **Yes** |
| Two-sided marketplace on day 1? | **No** — cold-start, trust, and legal risk too high |
| Best first model? | **Curated ADP Data Store** — you sell packs |
| What to sell? | Vertical synthetic packs + quality report + `spec.yaml` |
| Price range? | $19–$499 one-time; $49–$199/mo subscription |
| Key differentiator? | Quality score + FK guarantee + spec to regenerate |
| Timeline to launch? | 2–4 weeks (package existing examples + Gumroad) |

**Positioning:** *The store for business-ready synthetic data — FK-safe, quality-scored, commercially licensed, with the spec to regenerate.*

---

## 1. Market opportunity

The AI training data market was **~$2.8B in 2024**, projected to **$9.6B by 2029** (~28% CAGR).

| Marketplace | Model | Commission |
|-------------|-------|------------|
| AWS Data Exchange | 3,000+ data products | 15–30% |
| Snowflake Marketplace | Subscription datasets | ~10% |
| Databricks Marketplace | ML-optimized datasets | Platform fee |
| Hugging Face | Free + paid datasets | Tips / discovery |
| PatientDatasets.com | Niche synthetic packs | Direct — from **$49** |

Buyers pay when they need data **fast**, with **clear licensing**, without building pipelines.

---

## 2. Why people buy pre-built data

| Motivation | Willingness to pay |
|------------|-------------------|
| Speed — need data today | High |
| No engineering — don't want to run generators | High |
| Trusted quality — FK-safe, realistic | Medium–High |
| Commercial license — legal clarity | High |
| Vertical specificity — retail, healthcare | High |

**CFO logic:** $49–$499 is cheap vs 2–5 days of engineer time ($2K–$10K).

---

## 3. What works vs what fails

### Models that work

| Model | Example | Why |
|-------|---------|-----|
| Curated vertical packs | PatientDatasets ($49+) | Clear use case, commercial license |
| Platform listings | AWS Data Exchange | Trust, S3 delivery, billing solved |
| Generation API | Gretel, MockHero | Custom data on demand |
| Try-before-buy samples | 1K-row preview | Reduces Arrow paradox |
| Quality certificates | Score + FK report | Trust without full disclosure |

### Why generic marketplaces fail

1. **Arrow Information Paradox** — buyer can't judge value without seeing data
2. **Trust gap** — "Is this data actually good?"
3. **Cold-start** — need sellers and buyers at launch
4. **Commoditization** — race to bottom
5. **Disintermediation** — buy once, redistribute
6. **Legal risk** — licensing, re-identification unclear

---

## 4. ADP advantages

| Capability | Marketplace value |
|------------|-------------------|
| Spec-driven generation | Sell custom data on demand, not only static files |
| Quality score (0–100) | Trust mechanism before full purchase |
| FK-safe guarantee | vs Faker / Kaggle free data |
| Seasonality engine | Premium retail / time-series packs |
| Semantic model (Cube.js) | Bundle "data + metrics layer" |
| Multiple formats | Parquet, CSV, DuckDB |
| Vertical examples | Retail, SaaS CRM ready to package |
| MCP integration | "Generate and buy" in one agent flow |

**Hybrid model:** Sell **pre-built packs** AND **on-demand generation** — stronger than either alone.

---

## 5. Recommended rollout

### Phase 1 — ADP Data Store (start here)

You as sole seller. Curated packs, not two-sided.

```
FREE TIER          │  PAID PACKS         │  CUSTOM
1K row samples     │  $19–$499 one-time  │  $0.50/100K rows
per vertical       │  100K–10M rows      │  Team+ API
Community license  │  Commercial license │  Usage-based
```

See [DATA-STORE-SKUS.md](./DATA-STORE-SKUS.md) for launch catalog.

### Phase 2 — Template marketplace (3–6 months)

Third parties sell **spec templates + research notes** (not raw data). ADP takes 20–30% commission. Buyer still runs ADP to generate — keeps platform moat.

### Phase 3 — Full two-sided marketplace (12–24 months)

Creators list datasets. ADP handles hosting, billing, quality verification. 70/30 revenue split. Requires legal framework and fraud prevention.

---

## 6. Pricing models

| Model | Price range | Best for |
|-------|-------------|----------|
| One-time pack | $19–$499 | SMB, students, POC |
| Monthly subscription | $49–$199/mo | Teams needing fresh data |
| Usage-based | $0.10–$0.50 / 100K rows | Developers, APIs |
| Enterprise license | $5K–$50K/yr | Unlimited + custom domains |
| Marketplace commission | 15–30% | Third-party sellers |

---

## 7. Legal requirements

| Requirement | ADP status |
|-------------|------------|
| Commercial license terms | See [templates/DATASET-LICENSE.md](./templates/DATASET-LICENSE.md) |
| Synthetic-only warranty | ✅ Generated from spec, no real PII |
| Quality disclaimer | ✅ Quality score + report |
| Free sample preview | Planned — 1K rows |
| No resale clause | In license template |
| Payment (Stripe/Gumroad) | Not built yet |

**Provenance advantage:** Spec-generated (cold-start) data has cleaner legal story than data synthesized from prod samples.

---

## 8. Distribution channels

| Channel | Effort | When |
|---------|--------|------|
| Gumroad / Lemon Squeezy | Low | Week 1 |
| Hugging Face Datasets | Low | Week 2 (discovery) |
| ADP website store | Medium | Month 2 |
| AWS Data Exchange | High | Month 3+ (10+ SKUs) |
| Snowflake Marketplace | High | Phase 2 |

---

## 9. Revenue potential

### Year 1 (Data Store only)

| Stream | Monthly | Annual |
|--------|---------|--------|
| 50 × Retail Starter @ $19 | $950 | |
| 20 × Retail Pro @ $99 | $1,980 | |
| 30 × Healthcare @ $49 | $1,470 | |
| 15 × SaaS CRM @ $79 | $1,185 | |
| 10 × Team API @ $199 | $1,990 | |
| **Total** | **~$7,500** | **~$90K** |

### Year 2 (store + AWS + templates)

Direct store $150K + AWS $50K + templates $20K + subscriptions $120K ≈ **$340K/yr**

---

## 10. Launch plan (4 weeks)

### Week 1–2 — Package assets
- Export `seasonal-retail`, `retail-ecommerce`, `customer-transaction` as paid tiers
- Quality PDF + data dictionary per pack
- Commercial license from template

### Week 3 — Store
- Gumroad or Lemon Squeezy storefront
- Free 1K-row samples on GitHub
- Hugging Face listings

### Week 4 — Marketing
- r/dataengineering, dbt Slack, BI communities
- Pair with [OUTBOUND-TEMPLATES.md](./OUTBOUND-TEMPLATES.md)

---

## 11. Competitive gap

No dominant player owns: **"Buy FK-safe business data with quality proof and Cube semantic model."**

| Player | Gap ADP fills |
|--------|---------------|
| Kaggle / Hugging Face | Commercial license + quality score |
| PatientDatasets | Multi-vertical + generation API |
| Faker / SDV | FK-safe + scored + semantic layer |
| SynthForge / Unicourn | Paid premium + vertical depth + spec reuse |

---

## Related docs

- [DATA-STORE-SKUS.md](./DATA-STORE-SKUS.md) — launch SKU listings
- [templates/DATASET-LICENSE.md](./templates/DATASET-LICENSE.md) — commercial license
- [PRICING.md](./PRICING.md) — subscription tiers
- [MARKET-RESEARCH.md](./MARKET-RESEARCH.md) — buyer research
- [PRODUCT-ROADMAP.md](./PRODUCT-ROADMAP.md) — build phases
