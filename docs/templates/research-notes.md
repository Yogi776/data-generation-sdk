# Research Notes Template

Fill this during domain research before calling `propose_spec(description, research_notes)`.

## Domain

- **Domain:**
- **Locale:**
- **Date researched:**

## Sources

| # | Source | URL | Year | What it informs |
|---|--------|-----|------|-----------------|
| 1 | | | | |

## Category distributions

| Category | Target % | Source # | Notes |
|----------|----------|----------|-------|
| | | | |

## Numeric ranges

| Metric | Min | Mean | Max | Currency/unit | Source # |
|--------|-----|------|-----|---------------|----------|
| | | | | | |

## Business rules

| Rule | Rate / constraint | Source # |
|------|-------------------|----------|
| Return rate | | |
| Fraud rate | | |
| Status mix | | |

## Entities (proposed)

| Table | Grain | Key relationships |
|-------|-------|-------------------|
| | | |

## KPI targets (for post-generation SQL verify)

| KPI | Target | SQL sketch |
|-----|--------|------------|
| Payment mix — UPI | % | `SELECT payment_method, COUNT(*) ...` |
| AOV | currency | `SELECT AVG(order_total) ...` |

## Agent checklist

- [ ] User approved research table
- [ ] Weights sum to 100% per categorical column
- [ ] Passed to `propose_spec` as `research_notes`
