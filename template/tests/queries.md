---
type: guidance
title: "Retrieval smoke tests"
description: "Questions this bundle must answer, and the page expected to answer each."
classification: P1
tags: [guidance, tests]
generated:
  by: wiki-kit/0.1
  at: "2026-08-25"
---
# tests/queries.md

Retrieval smoke tests. Each row: a question a reader should be able to answer
from this bundle, and the page that answers it. Run them by hand (or ask the
agent) after big ingests; a miss means `index.md` or the page needs work.

| Question | Expected page |
|---|---|
| How do I restart the mail relay? | `/runbooks/restart-mail-01.md` |
| What gets backed up and how often? | `/concepts/backup-strategy.md` |
| What is mail-01? | `/systems/mail-01.md` |
