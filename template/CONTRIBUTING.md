---
type: guidance
title: "Contributing"
description: "How humans feed sources into this bundle and review the agent's PRs."
classification: P1
tags: [guidance]
generated:
  by: wiki-kit/0.1
  at: "2026-08-25"
---
# Contributing

This bundle is written by an agent and reviewed by humans. See `CLAUDE.md` for
the agent's rules.

## Humans

1. Drop sources into `raw/notes/`, `raw/tickets/`, or `raw/meetings/` as
   `YYYY-MM-DD-title.md` with `status: new` frontmatter (see `raw/CLAUDE.md`).
2. Ask the agent to ingest. It opens a PR on an `ingest/<date>-<slug>` branch.
3. Review the PR. Check citations against the source. Merge or request changes.
4. Only humans add `verified:` frontmatter and lower a `classification:`.

## Setup (once per clone)

```sh
pre-commit install
```

Pre-commit runs gitleaks and the wiki-kit lint container on every commit.
The same lint runs in CI on every PR; it must pass before merge.

## Never

- Commit directly to `main`.
- Edit files under `raw/` once `status: ingested`.
- Delete a wiki page; set `status: deprecated` instead.
