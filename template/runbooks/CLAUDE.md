# runbooks/CLAUDE.md

A runbook is a procedure a junior can execute alone, in order, without asking anyone.
If it needs judgement calls, it is not a runbook; it is a concept page that links
to runbooks.

## Naming

`<verb>-<object>.md`. `restart-mail-01.md`, `rotate-okta-api-key.md`,
`onboard-new-laptop.md`.

## Required frontmatter

```yaml
type: Runbook
stale_after: YYYY-MM-DD     # REQUIRED. 6 months from generated.at unless source says
owners: [human:<id>]        # REQUIRED
knows: [human:<id>]         # REQUIRED. Who has run this successfully.
systems: [/systems/mail-01.md]
ticket: <if written from an incident>
```

## Required headings, in this order

Lint fails without all four.

```markdown
# Before you start
Access needed. Tools needed. Time window. Who to tell. What to check first.

# Steps
1. Numbered. One action per step. Exact commands in fenced blocks.
2. Expected output after each command that has output.
3. Placeholders in `<angle-brackets>`, never example real values.

# How you know it worked
Concrete checks. Commands with expected output. What the user should see.

# Rollback
How to undo each step that changed state. If a step cannot be undone, say so
in `# Before you start` as a warning.
```

Optional: `# Escalation` (who to page, when), `# Notes` (dated, footnoted).

## Rules

- Every step that changes state has a matching rollback line.
- Commands are copied from a source, footnoted. You do not invent commands. If the
  source describes an action without the exact command, write `<command: see owner>`
  and flag it in the PR.
- A junior running this in a test environment is the quarterly test. If they file a
  gap as a `raw/` source, fold it in and bump `generated.at`. Do not touch
  `stale_after`; a human resets it on `verified:`.
- Never merge two runbooks into one because they look similar.
