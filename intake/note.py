#!/usr/bin/env python3
"""note.py — turn form values into a raw/ file.

Shape is fixed by template/raw/CLAUDE.md: no `title` key (the title is the
H1), `kind` selects the directory, and the key order below is the documented
one. Filenames are YYYY-MM-DD-<slug>.md; anything else is a lint error the
human would have to fix, which is the whole point of generating it here.

Every user-supplied scalar is emitted with json.dumps: a JSON string literal
is a valid YAML double-quoted scalar, so a value containing `: `, a newline,
a leading `#` or a quote stays one string and cannot forge a second key.
"""
from __future__ import annotations

import json
import re

from config import Form

SLUG_MAX = 50
# raw/CLAUDE.md pluralizes the directory but not the frontmatter value.
KIND_DIR = {"note": "notes", "ticket": "tickets",
            "meeting": "meetings", "vendor": "vendor"}


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:SLUG_MAX].strip("-") or "note"


def author_from_email(email: str) -> str:
    return "human:" + email.split("@", 1)[0]


def note_path(kind: str, day: str, slug: str) -> str:
    return f"raw/{KIND_DIR[kind]}/{day}-{slug}.md"


def render(*, title: str, kind: str, author: str, day: str,
           classification: str, ticket: str | None, form: Form,
           values: dict[str, str]) -> str:
    lines = ["---", "type: Source", f"kind: {kind}", f"author: {author}",
             f"date: {day}", f"classification: {classification}"]
    if ticket:
        lines.append(f"ticket: {json.dumps(ticket)}")
    lines.append("status: new")
    for f in form.fields:
        value = (values.get(f.name) or "").strip()
        if f.into == "frontmatter" and value:
            lines.append(f"{f.name}: {json.dumps(value)}")
    lines += ["---", "", f"# {title}", ""]
    for f in form.fields:
        value = (values.get(f.name) or "").strip()
        if f.into == "body" and value:
            lines += [f"## {f.label}", "", value, ""]
    return "\n".join(lines).rstrip("\n") + "\n"
