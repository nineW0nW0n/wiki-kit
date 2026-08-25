---
type: guidance
title: "decisions/ rules"
description: "How decision pages link to assumptions and get reviewed."
tags: [guidance]
generated:
  by: wiki-kit/0.1
  at: "2026-08-25"
---
# decisions/CLAUDE.md

One page per decision. A decision is anything a human chose that other pages depend
on: a vendor, an architecture, a policy, a schedule. Decisions are living objects:
their assumptions are tracked and can break.

## Naming

`YYYY-MM-DD-<slug>.md`, or `<ticket>.md` when a change ticket is the decision record.

## Required frontmatter

```yaml
type: Decision
decided_on: YYYY-MM-DD
decided_by: [human:<id>]
decision_status: active      # active | superseded | reversed
supersedes: /decisions/...   # optional
assumptions:
  - /assumptions/<slug>.md
ticket: <CHG… if applicable>
```

## Body template

```markdown
# Decision
One sentence. What was chosen.[^src]

# Context
Why it came up. What the alternatives were.

# Assumptions
* [Vendor X supports LDAP](/assumptions/vendor-x-supports-ldap.md) — holding
(mirror of frontmatter; the status word is copied from the assumption page)

# Consequences
What this decision forces elsewhere. Link the systems and runbooks it shaped.

# Review log
* YYYY-MM-DD — reviewed because assumption X weakened; outcome: kept.
```

## Rules

- You never change `decision_status`. You create a `reviews/` file when an assumption
  under this decision weakens or breaks; a human changes the status.
- Every assumption listed in frontmatter has a page in `assumptions/`. Create the
  stub if missing.
- The `# Assumptions` status words are derived from the assumption pages. When you
  update an assumption, update every decision that mirrors it, same commit.
- A decision with zero assumptions is a lint warning: either it has hidden
  assumptions or it is a fact, not a decision.
