---
name: adp-spec-author
description: Author and review ADP dataset spec YAML with user approval gates. Use for propose_spec, apply_spec, joins, weights, values_by, and spec validation before generation.
---

# ADP Spec Author

## Steps

1. Call `propose_spec(description, research_notes)` OR draft from `retail/spec.yaml` / `examples/` patterns
2. Review YAML:
   - Joins and cardinalities
   - `values_by` column order matches parent keys
   - `after` / `expr` / `null_unless` dependencies
   - No `format` on name/email columns — use built-in samplers
3. User approves weights and cardinalities
4. **Only then** call `apply_spec`

## Rules

- `propose_spec` never applies automatically — always show YAML for review.
- Match researched distribution weights where possible.
- Reference retail spec for production-grade patterns.
