# Raw intake: a web form for people who do not use git

Status: approved design, not yet implemented
Date: 2026-08-27

## Problem

Getting raw information into a `brain-*` bundle currently means cloning the repo,
writing OKF frontmatter by hand, and committing. That is fine for the people who
already work in the repo and a hard stop for everyone else. Incident write-ups,
meeting notes and vendor answers stay in chat logs and inboxes because the cost of
filing them correctly is higher than the cost of not filing them at all.

This design adds a browser form, behind Cloudflare Access, that turns a filled-in
form into a correctly shaped `raw/` file and opens a pull request against the
bundle repo. Field definitions live in the bundle, so the form changes without a
deploy.

## Decisions taken

Four choices were settled before this design and are not reopened here:

1. **Web form on the wiki**, not GitHub Issue Forms, not a local CLI. The point is
   to serve people who do not have or want a GitHub account.
2. **Field definitions live in the bundle repo**, in `intake.yml` at its root.
   Adding a field is a commit to the bundle, not a node change.
3. **Every submission becomes a branch and a pull request.** Nothing is written to
   a default branch by this service.
4. **A separate `intake` container**, not a new capability inside `mcp`.

Choice 4 has a cost worth stating plainly. HANDOFF's invariant is that the
container never writes to a bundle repo. This design does not delete that
invariant, it narrows it: `builder` and `mcp` keep read-only mounts and read-only
credentials, and a single new service — separately credentialed, separately
exposed, holding no writable volume — performs writes through the GitHub API. The
alternative that preserves the invariant completely is a client-side form that
deep-links to GitHub's "create new file" page, which requires every submitter to
have repo access. That alternative is recorded here as the fallback if the write
token ever proves unacceptable.

No new Python dependencies are required. `mcp==2.1.0` already brings `starlette`,
`uvicorn`, `python-multipart` and `httpx2`, which is the whole runtime need. This
satisfies the tool acceptance rule in HANDOFF §2 without adding a line to
`requirements.txt`.

## Configuration: `intake.yml`

The service reads `/bundles/<id>/intake.yml` from the existing read-only mount the
builder refreshes each cycle. A field added to a bundle appears on its form within
one `interval_seconds` (900s by default), with no restart and no node access.

```yaml
title: "Drop a note"                 # form heading; optional
fields:
  - name: summary
    label: "What happened?"
    type: textarea                   # text | textarea | select | date | checkbox
    required: true
    into: body                       # body | frontmatter
  - name: system
    label: "Which system?"
    type: select
    options: [mail-01, db-01]
    into: frontmatter
```

Five field types. No file uploads in v1: `raw/` is markdown, and attachments need a
storage story this system does not have.

`kind` is reserved as a field name but still has to be chosen, since it selects the
directory. It is set one of two ways, never as an `intake.yml` field:

```yaml
kind: note                 # pin every submission in this bundle to one kind
# or
kind: [note, meeting]      # render a built-in selector limited to these kinds
```

Omitting the key entirely renders the selector over all four kinds. The selector is
built in, so its value always reaches the generated frontmatter rather than the
user-defined block, and the reserved-name check stays absolute.

A bundle with no `intake.yml` gets a built-in default form: a title and one
free-text box. A bundle whose `intake.yml` does not parse gets an error page and
refuses submission — it does not silently fall back to the default, because
accepting input under a configuration the owner believes is live is how notes end
up in the wrong shape.

## Generated frontmatter and the notice block

`template/raw/CLAUDE.md` pins the shape of a raw file. Note that it has no `title`
key: the title is the `# H1`, and `kind` selects the directory.

```yaml
---
type: Source
kind: note | ticket | meeting | vendor
author: human:<id>
date: YYYY-MM-DD
classification: P1 | P2 | P3
ticket: <optional, must match the bundle's regex>
status: new | ingested
---
```

Six of these keys are generated and are **reserved**: `type`, `kind`, `author`,
`date`, `classification`, `status`. An `intake.yml` that declares a field with one
of those names causes the form to refuse to render, naming the collision, rather
than letting a form overwrite frontmatter the lint rules depend on.
`classification` comes from the bundle's tier, so a submitter cannot accidentally
under-classify.

Every form opens with a notice block showing what will actually be committed:

```
This will be committed as raw/notes/2026-08-27-<slug>.md

---                              Reserved — cannot be used as
type: Source                     field names in intake.yml:
kind: note
author: human:abcollado.28         type    kind    author
date: 2026-08-27                   date    classification   status
classification: P1
status: new                      ticket is allowed, but is validated
---                              against this bundle's ticket_regex
```

The block is rendered from the same constants the validator uses, so it cannot
drift from what is written. Values known at render time are shown real; `<slug>`
stays a placeholder because it derives from the title. Making the slug track
typing costs roughly twenty lines of vanilla JavaScript and is deliberately not in
v1.

`ticket` is the one user-supplied field with special handling: it is validated
against the bundle's `ticket_regex` from `bundles.yml` before any API call, with
the error shown inline. Lint rule 4 would otherwise fail the pull request where the
person who typed it will never see it.

## Submit path

**Filename.** `raw/<kind>/<YYYY-MM-DD>-<slug>.md`, per the layout rule in
`raw/CLAUDE.md`. The slug is derived from the title: lowercased, non-alphanumerics
folded to `-`, collapsed, trimmed, capped at 50 characters. A title that yields an
empty slug falls back to `note`.

**Collision.** A contents `PUT` without a `sha` returns 422 if the path exists.
That is the collision check; no extra probe call is made. On 422 the service
retries as `-2`, `-3`, up to five attempts, then reports a clear error.

**Body.** `# <title>`, then one `## <label>` section per `into: body` field in
`intake.yml` order. Fields marked `into: frontmatter` are appended after the six
generated keys. Empty optional fields are omitted rather than written as empty
sections.

**API calls, in order.** `GET git/ref/heads/<branch>` for the base sha,
`POST git/refs` to create `intake/<date>-<slug>`, `PUT contents/<path>` on that
branch, `POST pulls`. Owner and repository come from the bundle's `repo:` URL in
`bundles.yml`. The pull request body records the submitter's Access email and which
fields were filled.

**On failure.** The form re-renders with every value still in place. Losing a typed
incident write-up to a 500 is the fastest way to make someone stop using this. If
the branch was created but the file `PUT` failed, the ref is deleted on a
best-effort basis so the repository does not collect orphan branches.

## Authentication and exposure

Exposure mirrors `/mcp`. Intake listens on `:8082` inside the compose network only.
Caddy routes `/intake*` in the `:8090` tunnel block; the `:8080` block answers 403
exactly as it does for `/mcp`. The published LAN port cannot reach intake, so a
forged `Cf-Access-*` header from the LAN is worthless.

Caddy strips any client-supplied `X-Wiki-User` and rewrites it from
`Cf-Access-Authenticated-User-Email`, reusing the existing `header_up` pair. Intake
rejects an empty `X-Wiki-User` with 403.

That rule is stricter than MCP's on purpose. HANDOFF §9 records that service tokens
carry no user email; MCP still serves them for bundles without a `readers:` list.
Intake refuses them outright, because `author: human:<id>` is required and a service
token cannot supply a human. Automation that wants to write notes should use the
GitHub API with its own identity.

Which bundles a person sees reuses the `readers:` allowlist logic already in
`mcp/server.py` (`_allowed`) — the same header, the same semantics, no second
authorization model to keep in sync.

**Access policy.** The existing `humans` policy on the hostname already covers
`/intake`. A second application scoped to the `/intake` path, with its own policy,
makes "can read the wiki" and "can file into the wiki" separately grantable. Without
it, every reader is a writer.

**Token.** A second fine-grained PAT, distinct from the builder's read-only one:

- Repository access: the `brain-*` repos only, never `wiki-kit`
- Contents: read and write; Pull requests: read and write; everything else: none
- Delivered as `INTAKE_TOKEN`, mounted only into the intake container

`builder` keeps its read-only `GIT_TOKEN`. `mcp` gets neither. Intake mounts
`/bundles` and `bundles.yml` read-only and nothing else: no `/site`, no `/state`, no
Docker socket, no writable volume.

**Branch protection is load-bearing.** The token can push branches. What stops it
reaching a default branch is a protection rule on `main` in each `brain-*` repo
requiring a pull request. Without that rule this design's security story reduces to
"the token is polite". Enabling it is a numbered rollout step, not a footnote.

**Blast radius if the node is fully compromised:** read every `brain-*` repo (already
true today through the pull token), plus create branches and open pull requests. Not:
merge, force-push, reach `wiki-kit`, or reach Actions secrets.

**CSRF.** Access cookies are ambient, so a malicious page in a logged-in submitter's
browser could auto-POST to `/intake`. The impact is bounded to a pull request someone
must merge, and the fix is small: reject any POST whose `Sec-Fetch-Site` is not
`same-origin`, with an `Origin` check as the fallback for older browsers.

## Failure modes

The one that matters most is silent token expiry. Fine-grained PATs expire, and the
failure mode is a colleague typing up an incident, hitting Submit, seeing an error
they do not understand, and quietly never returning. Intake exposes `/intake/health`,
which makes one cheap authenticated call and reports `ok`, `expired` or
`unreachable`. The builder calls `http://intake:8082/health` directly over the compose
network once per cycle and folds the answer into `status.json`, where bundle build
state already surfaces. It is deliberately not routed through Caddy: the check is
service-to-service and needs no Access identity.

| Condition | Behaviour |
|---|---|
| `bundles.yml` missing or unparseable | refuse to start, loudly, matching the builder |
| one bundle's `intake.yml` malformed | that bundle's form errors; others keep working |
| submitter allowed on no bundle | explanatory page, not an empty form |
| bundle configured but not yet cloned | not offered in the bundle list |
| slug collides | `-2` … `-5`, then a clear error |
| title is all emoji or punctuation | slug falls back to `note`; collision path handles repeats |
| oversized paste | capped at 512 KB with a message; the contents API is unhappy past ~1 MB |
| pull request opens but lint fails on it | submitter does not see it; the PR body carries their email so the owner knows who to ask |

The last row is an accepted v1 limitation, recorded so it is a choice rather than an
oversight.

## Testing

`tests/test_intake.py` covers the pure functions with the GitHub client injected, so
nothing touches the network: slug generation, frontmatter key order against
`template/raw/CLAUDE.md`, reserved-name collision, `ticket_regex` validation, and
malformed-configuration handling.

The test that earns its keep generates a note into a temporary copy of
`fixtures/good-bundle`, then runs `scripts/lint.py --strict` over the result and
asserts it passes. That ties intake's output to the §6 rules directly: a lint rule
change breaks intake's tests rather than breaking submissions in production.

`tests/compose-test.sh` gains the mirror of its existing `/mcp` assertion —
`:8080/intake` returns 403, `:8090/intake` returns form HTML — with `GITHUB_API`
pointed at a local stub so the compose test stays offline, as the seeded bare repo
keeps it offline today. No new CI job: the existing `test` and `smoke` jobs pick both
up.

## Rollout

Each step is independently green, in the style of HANDOFF §11.

| Step | Deliverable | Green when |
|---|---|---|
| 1 | `intake.yml` schema, parser, reserved-name check | `pytest tests/test_intake.py` passes; no service yet |
| 2 | Frontmatter and body assembly | the lint round-trip test passes `--strict` |
| 3 | Starlette app: GET form, notice block, bundle list via `_allowed` | form renders; POST returns a dry-run preview and writes nothing |
| 4 | GitHub client and real POST wiring | opens a PR against a scratch repo with `INTAKE_DRY_RUN=0` |
| 5 | Caddy routes, compose service | `compose-test.sh` asserts 403 on `:8080/intake`, HTML on `:8090/intake` |
| 6 | Token, Access policy, branch protection | three new `deploy_wizard.sh` stages walked end to end on the node |
| 7 | Dry-run off, default `intake.yml` in `template/`, docs | a non-git colleague files a note and it lands as a PR |

Step 6 belongs in `deploy_wizard.sh` rather than a new document: the Cloudflare and
GitHub steps are human-only clicks, which is exactly what that wizard exists for.
