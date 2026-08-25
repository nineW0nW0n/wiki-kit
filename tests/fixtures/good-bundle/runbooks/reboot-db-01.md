---
type: Runbook
title: "Reboot db-01"
description: "Reboot the test database server."
classification: P1
status: draft
owners: [human:pat.db]
knows: [human:pat.db]
stale_after: 2099-01-01
systems: [/systems/db-01.md]
tags: [test]
generated:
  by: wiki-kit/0.1
  at: "2026-01-01"
sources:
  - id: db-01-baseline
    resource: /raw/notes/2026-01-01-db-01-baseline.md
    title: "db-01 baseline notes"
---

# Before you start

SSH access to [db-01](/systems/db-01.md) as an operator.[^db-01-baseline]

# Steps

1. Reboot:

   ```sh
   sudo systemctl reboot
   ```

# How you know it worked

Host answers ping within five minutes.[^db-01-baseline]

# Rollback

A reboot has nothing to undo.[^db-01-baseline]

[^db-01-baseline]: db-01 baseline notes
