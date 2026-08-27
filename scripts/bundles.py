#!/usr/bin/env python3
"""bundles.py — the one reader for bundles.yml.

Shared by the MCP server and the intake service so that "which bundles may
this caller see" has exactly one implementation. A bundle with no `readers:`
key is visible to every authenticated caller; a bundle with `readers:` is
visible only to the listed emails (HANDOFF §9).
"""
from __future__ import annotations

from pathlib import Path

import yaml


def load(path: Path) -> dict:
    """Parse bundles.yml. An empty file is an empty config, not an error."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def allowed_ids(cfg: dict, user: str) -> list[str]:
    out = []
    for b in cfg.get("bundles", []):
        readers = b.get("readers")
        if readers is None or user in readers:
            out.append(str(b["id"]))
    return out


def by_id(cfg: dict, bid: str) -> dict | None:
    for b in cfg.get("bundles", []):
        if str(b["id"]) == bid:
            return b
    return None
