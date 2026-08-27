#!/usr/bin/env python3
"""config.py — read a bundle's intake.yml into a Form.

The form's shape lives in the bundle repo, so adding a field is a commit to
the bundle rather than a change on the node. A bundle with no intake.yml gets
a default single-textarea form; a bundle with a broken one gets an error page
and no submissions, because accepting input under a config the owner believes
is live is how notes end up in the wrong shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from pathlib import Path

import yaml

# Generated frontmatter keys. A user-defined field may never use these names.
RESERVED = ("type", "kind", "author", "date", "classification", "status")
FIELD_TYPES = ("text", "textarea", "select", "date", "checkbox")
KINDS = ("note", "ticket", "meeting", "vendor")


class ConfigError(Exception):
    """intake.yml is present but unusable. The message is shown to the user."""


@dataclass
class Field:
    name: str
    label: str
    type: str
    required: bool = False
    into: str = "body"
    options: list[str] = dc_field(default_factory=list)


@dataclass
class Form:
    title: str
    kinds: list[str]
    fields: list[Field]


DEFAULT = Form(
    title="Drop a note",
    kinds=list(KINDS),
    fields=[Field(name="body", label="Anything you want to record",
                  type="textarea", required=True, into="body")],
)


def _kinds(raw) -> list[str]:
    if raw is None:
        return list(KINDS)
    values = raw if isinstance(raw, list) else [raw]
    out = []
    for v in values:
        v = str(v)
        if v not in KINDS:
            raise ConfigError(f"unknown kind {v!r}; allowed: {', '.join(KINDS)}")
        out.append(v)
    if not out:
        raise ConfigError("`kind:` is empty; omit the key to allow every kind")
    return out


def _field(raw, seen: set[str]) -> Field:
    if not isinstance(raw, dict):
        raise ConfigError(f"each entry under `fields:` must be a mapping, got {raw!r}")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ConfigError("a field is missing `name`")
    if name in RESERVED:
        raise ConfigError(
            f"field name {name!r} is reserved: {', '.join(RESERVED)} are generated")
    if name in seen:
        raise ConfigError(f"duplicate field name {name!r}")
    seen.add(name)

    ftype = str(raw.get("type", "text"))
    if ftype not in FIELD_TYPES:
        raise ConfigError(
            f"field {name!r} has unknown type {ftype!r}; "
            f"allowed: {', '.join(FIELD_TYPES)}")

    into = str(raw.get("into", "body"))
    if into not in ("body", "frontmatter"):
        raise ConfigError(f"field {name!r}: `into` must be body or frontmatter")

    options = [str(o) for o in (raw.get("options") or [])]
    if ftype == "select" and not options:
        raise ConfigError(f"field {name!r} is a select but has no `options`")

    return Field(name=name, label=str(raw.get("label", name)), type=ftype,
                 required=bool(raw.get("required", False)), into=into,
                 options=options)


def load(bundle_dir: Path) -> Form:
    path = Path(bundle_dir) / "intake.yml"
    if not path.is_file():
        return DEFAULT
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"intake.yml could not be read: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("intake.yml must be a mapping at the top level")

    seen: set[str] = set()
    fields = [_field(f, seen) for f in (raw.get("fields") or [])]
    return Form(title=str(raw.get("title", "Drop a note")),
                kinds=_kinds(raw.get("kind")), fields=fields)
