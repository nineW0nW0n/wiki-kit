---
type: Concept
title: "Backup strategy"
description: "Sample concept page: what gets backed up, where, how often. Replace on first real ingest."
classification: P1
status: draft
tags: [sample, backup]
generated:
  by: wiki-kit/0.1
  at: "2026-08-25"
sources:
  - id: mail-01-baseline
    resource: /raw/notes/2026-08-25-mail-01-baseline.md
    title: "mail-01 baseline notes"
---

# What it is

Nightly configuration backups of every system page's subject to the backup
host; files-as-truth means application data is restored from Git, not from
images.[^mail-01-baseline]

# Covered systems

* [mail-01](/systems/mail-01.md) — config only

[^mail-01-baseline]: mail-01 baseline notes
