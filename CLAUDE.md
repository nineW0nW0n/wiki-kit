# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read HANDOFF.md first

`HANDOFF.md` is the settled spec for this repo — architecture, stack choices, lint
rules, and a step-by-step build plan (§11). Decisions there are final; do not
re-litigate them (including the rejected-tools list in §3). Items marked **VERIFY**
must be checked at the step named, not assumed. Follow the build steps in order;
do not advance until the current step's acceptance criteria are green; commit after
each step.

## What this repo is

`wiki-kit` is the public tooling half of a two-repo system: it produces one container
image (`ghcr.io/<owner>/wiki-kit`) that serves any number of private `brain-<domain>`
knowledge bundles (OKF v0.2 markdown). The image never contains knowledge, secrets,
or hostnames — bundles are cloned at runtime with a read-only token, and the container
never writes to a bundle repo.

Current state: early — only `HANDOFF.md` and `template/` exist. Most of the layout in
HANDOFF §4 (Dockerfile, `scripts/`, `mcp/`, `tests/`, CI) is still to be built.

## Key structure

- `template/` — copied verbatim into each new `brain-*` repo by `init.sh`. Its
  `CLAUDE.md` files use `{{BUNDLE_ID}}`-style placeholders and instruct the *bundle*
  agent, not this repo's agent. Every `CLAUDE.md` in a bundle is capped at 500 lines
  (lint rule 6) — keep template edits under that.
- `scripts/okf_validate.py`, `okf_init.py`, `okf_visualize.py` — vendored from
  `scaccogatto/okf-skills`; each file's header must record the source commit. Do not
  rewrite them; `lint.py` wraps the validator and adds the §6 rules on top.
- `bundles.yml` lives on the deployment node only; `bundles.example.yml` documents
  the schema (HANDOFF §5).

## Commands (per HANDOFF acceptance criteria)

```sh
python3 scripts/okf_validate.py template --strict   # OKF conformance (needs pyyaml)
python3 scripts/lint.py <bundle>                    # local lint; --pr --base <ref> in CI;
                                                    # --all --bundles bundles.yml in builder
pytest tests/test_lint.py                           # lint rule tests against tests/fixtures/
docker build .                                      # then: docker run … lint template
bash tests/smoke.sh
docker compose up                                   # curl :8080/eng/ → HTML; :8080/eng/index.md → raw md
```

## Constraints to keep in mind while building

- Tool acceptance rule (HANDOFF §2): new dependencies must be recent, credible,
  Apache-2.0/MIT, pinned (never `latest`), and removable without touching markdown.
- Files are truth: site, `wiki.db` search index, and MCP responses are all
  regenerated from markdown and disposable. Never make markdown depend on tooling.
- MCP server is read-only by construction — no write tool exists in the code.
- Same URL serves two representations: path ending `.md` → raw file for agents,
  otherwise → Quartz-built HTML for humans (Caddy routing, HANDOFF §8).
- Quartz build symlinks the bundle into `content/` (never copy with `-d`; it breaks
  the Explorer folder tree) and does an atomic swap into `/site/<id>`.
