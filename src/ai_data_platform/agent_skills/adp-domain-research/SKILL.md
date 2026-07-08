---
name: adp-domain-research
description: Web research workflow before propose_spec for realistic synthetic data. Use when grounding datasets in real-world distributions, market shares, or industry benchmarks.
---

# ADP Domain Research

Research **before** `propose_spec`. Use web search; cite sources.

## Collect

- Sources (URL + year)
- Category distributions with percentages
- Numeric ranges (mean, currency, quantities)
- Business rules (return rate, fraud rate, status mixes)

## Template

Use `docs/templates/research-notes.md` format. Pass findings as `research_notes` to `propose_spec(description, research_notes)`.

## Checkpoint

Present a research summary table to the user. **Get explicit approval** before drafting the spec.

Do not call `apply_spec` in this phase.
