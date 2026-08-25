---
type: guidance
title: "concepts/ rules"
description: "How idea, standard, pattern, and analysis pages are written."
tags: [guidance]
generated:
  by: wiki-kit/0.1
  at: "2026-08-25"
---
# concepts/CLAUDE.md

Ideas, standards, patterns, definitions, and filed analyses. Anything that is
"how we think about X" rather than "a thing" or "a procedure".

## Naming

`<slug>.md`. Nouns. `backup-strategy.md`, `naming-standard.md`.
`why-we-left-vendor-x.md` belongs in `decisions/`, not here.

## Types

```yaml
type: Concept     # a definition or explanation
type: Standard    # a rule the team follows; link the decision that set it
type: Pattern     # a reusable approach with examples
type: Analysis    # a filed answer from a query (root §4.2); sources are wiki pages
```

## Body

Free structure, but:

- First paragraph says what the concept is in plain words, with a footnote.
- `# Related` section at the end linking systems, runbooks, decisions that use it.
- Analyses carry `sources[]` pointing at the wiki pages they synthesized, not at
  `raw/`. Their `description` starts with "Answer to:".

## Rules

- When a concept is mentioned three or more times across the bundle and has no page,
  the lint pass creates a stub here with `status: draft` and one footnote.
- Do not write opinion. "Recommended" needs a decision page behind it.
