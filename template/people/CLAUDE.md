# people/CLAUDE.md

One page per person or vendor contact. This directory exists to answer "who knows
about X" and "who do I call". It is not an HR record.

## Naming

`<firstname-lastname>.md` for staff. `<vendor>-<role>.md` for vendor contacts.

## Required frontmatter

```yaml
type: Person            # or: Vendor Contact
classification: P2      # minimum. Never P1.
role: <title>
team: <team>
tags: []
```

No phone numbers, home addresses, personal email, or anything not needed to route a
work question. Work email and work chat handle are fine.

## Body template

```markdown
# Knows
* [mail-01](/systems/mail-01.md) — primary operator
* [Backups](/concepts/backup-strategy.md) — designed it

# Owns
* [thing](/systems/thing.md)

# Ask them about
Short bullets. What questions land well with this person.

# Handoff notes
Only filled when a human writes an offboarding source. Otherwise omit.
```

## Rules

- `# Knows` is derived. A person appears in a system's `knows:` list; you mirror it
  here. If they conflict, the system page wins and you fix this page.
- Never write anything evaluative about a person. Skill, availability, and
  responsibility are facts from sources; judgement is not.
- Pages here are `classification: P2` or higher. Lint enforces the floor.
