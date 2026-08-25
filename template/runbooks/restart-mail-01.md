---
type: Runbook
title: "Restart mail-01"
description: "Sample runbook: restart the mail relay service. Replace on first real ingest."
classification: P1
status: draft
owners: [human:sam.op]
knows: [human:sam.op]
stale_after: 2027-02-25
systems: [/systems/mail-01.md]
tags: [sample, mail]
generated:
  by: wiki-kit/0.1
  at: "2026-08-25"
sources:
  - id: mail-01-baseline
    resource: /raw/notes/2026-08-25-mail-01-baseline.md
    title: "mail-01 baseline notes"
---

# Before you start

SSH access to [mail-01](/systems/mail-01.md) as an operator. Announce in the ops
channel. No irreversible steps.[^mail-01-baseline]

# Steps

1. Check the queue depth:

   ```sh
   postqueue -p | tail -1
   ```

   Expected: a count line, or `Mail queue is empty`.[^mail-01-baseline]

2. Restart the service:

   ```sh
   sudo systemctl restart postfix
   ```

   No output on success.[^mail-01-baseline]

# How you know it worked

`systemctl is-active postfix` prints `active`, and a test mail from any app
arrives within one minute.[^mail-01-baseline]

# Rollback

Step 2 is a restart of a stateless service; nothing to undo. If the service
fails to start, `journalctl -u postfix -n 50` and escalate to the
owner.[^mail-01-baseline]

[^mail-01-baseline]: mail-01 baseline notes
