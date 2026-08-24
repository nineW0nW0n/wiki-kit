# systems/CLAUDE.md

One page per thing that can break: server, VM, container host, service, application,
network segment, vendor product, SaaS tenant.

## Naming

`<hostname-or-service-slug>.md`, lowercase, hyphens. `mail-01.md`, `okta.md`,
`vlan-40-servers.md`. If the thing has a hostname, the hostname is the filename.

## Required frontmatter (in addition to root §5)

```yaml
type: System            # or: Service | Application | Network | Vendor Product
resource: <URL or hostname if it has one>
owners: [human:<id>]    # accountable, one or more
knows: [human:<id>]     # anyone who can operate it without help; drives SPOF report
stale_after: YYYY-MM-DD # 12 months from generated.at unless a source says otherwise
tags: []
```

`knows` with a single entry puts the page on the Single Point of Failure list. That
is the intended behaviour; do not pad the list.

## Body template

```markdown
# What it is
One paragraph. What it does, who depends on it.[^src]

# Where it runs
Host, location, tier, IPs if classification allows.

# Depends on
* [thing](/systems/thing.md) — why

# Depended on by
* [thing](/systems/thing.md) — why

# Runbooks
* [Restart mail-01](/runbooks/restart-mail-01.md)

# Known issues
Dated bullets, newest first, each with a footnote.

# History
* YYYY-MM-DD — change, with footnote.
```

## Rules

- Every paragraph in `# What it is`, `# Where it runs`, and `# Known issues` carries
  a footnote. Lint warns on paragraphs without one.
- Never remove a `# Depended on by` entry because you did not see it in the current
  source. Absence of evidence is not evidence.
- If two sources disagree about this system, write both under `# Known issues` with
  their footnotes and file a `reviews/` entry.
