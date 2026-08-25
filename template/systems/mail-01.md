---
type: System
title: "mail-01"
description: "Sample system page: the internal mail relay. Replace on first real ingest."
classification: P1
status: draft
resource: mail-01.example.internal
owners: [human:sam.op]
knows: [human:sam.op]
stale_after: 2027-08-25
tags: [sample, mail]
generated:
  by: wiki-kit/0.1
  at: "2026-08-25"
sources:
  - id: mail-01-baseline
    resource: /raw/notes/2026-08-25-mail-01-baseline.md
    title: "mail-01 baseline notes"
---

# What it is

Internal SMTP relay for outbound application mail. Every app that sends mail
points at it; nothing else does.[^mail-01-baseline]

# Where it runs

VM on the office hypervisor, tier P1, no public interface.[^mail-01-baseline]

# Depends on

* [Backup strategy](/concepts/backup-strategy.md) — nightly config backup

# Depended on by

*(none recorded yet)*

# Runbooks

* [Restart mail-01](/runbooks/restart-mail-01.md)

# Known issues

* 2026-08-25 — queue fills when upstream relay rate-limits; restart clears
  it.[^mail-01-baseline]

# History

* 2026-08-25 — page created from baseline notes.[^mail-01-baseline]

[^mail-01-baseline]: mail-01 baseline notes
