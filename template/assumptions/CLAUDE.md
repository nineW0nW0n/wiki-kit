---
type: guidance
title: "assumptions/ rules"
description: "How assumption pages are named, structured, and re-statused."
classification: P1
tags: [guidance]
generated:
  by: wiki-kit/0.1
  at: "2026-08-25"
---
# assumptions/CLAUDE.md

One page per assumption. An assumption is a claim a decision depends on that could
turn out to be false. This directory is what makes decisions reviewable instead of
frozen.

## Naming

`<slug>.md`. A claim, not a topic. `vendor-x-supports-ldap.md`, not `vendor-x.md`.

## Required frontmatter

```yaml
type: Assumption
claim: <one sentence, falsifiable>
assumption_status: holding      # holding | weakened | broken | confirmed
decisions:
  - /decisions/<...>.md
evidence_for:
  - /systems/... or /concepts/...    # wiki pages, each footnoted from raw/
evidence_against: []
last_reviewed: YYYY-MM-DD
```

## Body template

```markdown
# Claim
Restate it. Say what would prove it false.

# Evidence
For: bullets with links and footnotes.
Against: bullets with links and footnotes.

# History
* YYYY-MM-DD — holding — created from [source](/raw/...)[^src]
* YYYY-MM-DD — weakened — [new test](/raw/...)[^src2] contradicts vendor claim
```

## Rules — the only place you change a status

1. On every ingest, ask of each assumption: does this source add evidence for,
   evidence against, or neither? Neither is the common case; move on.
2. If evidence changes, append a `# History` line. Never edit or delete old lines.
3. Then set `assumption_status`:
   - `holding`: no evidence against.
   - `weakened`: some evidence against, evidence for still stronger.
   - `broken`: evidence against outweighs. Must be backed by a source, not inference.
   - `confirmed`: a human set it. You never set `confirmed`.
4. On `weakened` or `broken`, create `reviews/YYYY-MM-DD-<slug>.md` listing the
   assumption, its decisions, and the evidence link. Update the status word mirrored
   in each decision page. Same commit.
5. Set `last_reviewed` to today whenever you touch the page.
6. You never move a status back toward `holding`. Only a human does, after review.
