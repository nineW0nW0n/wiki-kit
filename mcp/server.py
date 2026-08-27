#!/usr/bin/env python3
"""wiki-kit MCP server (HANDOFF §9). Read-only by construction: no write tool
exists, /bundles and /state are mounted read-only, wiki.db is opened mode=ro.

Auth: Caddy forwards Cloudflare Access's authenticated email as X-Wiki-User
(the server is reachable only over the compose network, so the header is
trustworthy). A bundle with a `readers:` list in bundles.yml is visible only
to those emails; a bundle without one is visible to every authenticated
caller. VERIFY(step 9): replace with Access group claims once confirmed.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

import yaml
from mcp.server.mcpserver import Context, MCPServer

sys.path.insert(0, str(Path(os.environ.get("APP_DIR", "/app")) / "scripts"))
import bundles  # noqa: E402  (shared bundles.yml reader)

BUNDLES_FILE = Path(os.environ.get("BUNDLES_FILE", "/etc/wiki/bundles.yml"))
BUNDLES_DIR = Path(os.environ.get("BUNDLES_DIR", "/bundles"))
DB = Path(os.environ.get("STATE_DIR", "/state")) / "wiki.db"
PORT = int(os.environ.get("MCP_PORT", "8081"))

mcp = MCPServer("wiki-kit")


def _user(ctx: Context) -> str:
    headers = ctx.headers or {}
    return next((v for k, v in headers.items() if k.lower() == "x-wiki-user"), "")


def _allowed(ctx: Context) -> list[str]:
    return bundles.allowed_ids(bundles.load(BUNDLES_FILE), _user(ctx))


def _frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(errors="replace")
        if not text.startswith("---\n"):
            return {}
        meta = yaml.safe_load(text[4:text.index("\n---", 4)])
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def _pages(bundles: list[str]):
    # ponytail: full walk per call; move to wiki.db columns if bundles get big
    for bid in bundles:
        root = BUNDLES_DIR / bid
        for p in sorted(root.rglob("*.md")):
            if ".git" in p.parts:
                continue
            yield bid, p.relative_to(root).as_posix(), _frontmatter(p)


@mcp.tool()
def search(query: str, bundle: str | None = None, ctx: Context = None) -> list[dict]:
    """Full-text search over all wiki pages. Optional bundle id to narrow."""
    allowed = _allowed(ctx)
    targets = [bundle] if bundle in allowed else allowed if bundle is None else []
    if not targets:
        return []
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(targets))
        rows = db.execute(
            "SELECT bundle, path, title, type, classification, "
            "snippet(pages, 5, '[', ']', '…', 12) FROM pages "
            f"WHERE pages MATCH ? AND bundle IN ({marks}) LIMIT 25",
            [query, *targets]).fetchall()
    finally:
        db.close()
    keys = ("bundle", "path", "title", "type", "classification", "snippet")
    return [dict(zip(keys, r)) for r in rows]


@mcp.tool()
def get_page(bundle: str, path: str, ctx: Context = None) -> str:
    """Return the raw markdown of one page, e.g. get_page('eng', 'index.md')."""
    if bundle not in _allowed(ctx):
        raise ValueError(f"unknown or unauthorized bundle: {bundle}")
    root = (BUNDLES_DIR / bundle).resolve()
    target = (root / path.lstrip("/")).resolve()
    if not target.is_relative_to(root) or ".git" in target.parts:
        raise ValueError(f"bad path: {path}")
    return target.read_text(errors="replace")


@mcp.tool()
def list_runbooks(bundle: str | None = None, ctx: Context = None) -> list[dict]:
    """List runbooks with owners and staleness dates."""
    allowed = _allowed(ctx)
    targets = [b for b in allowed if bundle in (None, b)]
    return [
        {"bundle": bid, "path": rel, "title": meta.get("title"),
         "owners": meta.get("owners"), "stale_after": str(meta.get("stale_after"))}
        for bid, rel, meta in _pages(targets)
        if rel.startswith("runbooks/") and not rel.endswith("CLAUDE.md")
    ]


@mcp.tool()
def who_knows(system: str, ctx: Context = None) -> list[dict]:
    """Who knows a system: pages naming it whose frontmatter lists knows/owners."""
    needle = system.lower()
    out = []
    for bid, rel, meta in _pages(_allowed(ctx)):
        names = [str(meta.get("title", "")).lower(), Path(rel).stem.lower()]
        people = meta.get("knows") or meta.get("owners")
        if people and any(needle in n for n in names):
            out.append({"bundle": bid, "path": rel, "knows": people})
    return out


@mcp.tool()
def trace_ticket(id: str, ctx: Context = None) -> list[dict]:
    """Every page whose frontmatter carries this ticket id."""
    return [
        {"bundle": bid, "path": rel, "title": meta.get("title")}
        for bid, rel, meta in _pages(_allowed(ctx))
        if str(meta.get("ticket", "")) == id
    ]


@mcp.tool()
def stale(ctx: Context = None) -> list[dict]:
    """Pages whose stale_after date has passed."""
    today = date.today().isoformat()
    out = []
    for bid, rel, meta in _pages(_allowed(ctx)):
        sa = meta.get("stale_after")
        sa = sa.isoformat() if isinstance(sa, date) else str(sa) if sa else None
        if sa and sa <= today:
            out.append({"bundle": bid, "path": rel, "stale_after": sa})
    return out


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=PORT)
