#!/usr/bin/env python3
"""lint.py — wiki-kit bundle lint.

Wraps the vendored okf_validate.py (rule 1) and adds the HANDOFF §6 rules on
top. Findings are tagged `[rule N]` so tests and humans can map them back to
the table. Exit non-zero on any ERROR; --strict promotes warnings.

Modes:
  lint.py <bundle> [--ticket-regex RE]            # laptop / pre-commit
  lint.py <bundle> --pr --base <ref> [--bot NAME] # CI on a bundle PR
  lint.py --all --bundles bundles.yml [--root D]  # builder, cross-links on
"""
from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml  # noqa: E402

import okf_validate as okf  # noqa: E402  (vendored, same directory)

CLASSIFICATIONS = {"P1", "P2", "P3"}
RUNBOOK_HEADINGS = ["Before you start", "Steps", "How you know it worked", "Rollback"]
CLAUDE_MD_MAX = 500
LINK_WARN = "cross-link target not found"


class Findings:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, rule: int, rel: str, msg: str) -> None:
        self.errors.append(f"[rule {rule}] {rel}: {msg}")

    def warn(self, rule: int, rel: str, msg: str) -> None:
        self.warnings.append(f"[rule {rule}] {rel}: {msg}")


def load_meta(path: Path) -> tuple[dict, str]:
    """Frontmatter dict + body. Empty dict when absent/unparseable (validator
    already reports that as rule 1)."""
    try:
        raw, body = okf.split_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return {}, ""
    if raw is None:
        return {}, body
    try:
        meta = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}, body
    return (meta if isinstance(meta, dict) else {}), body


def md_files(bundle: Path) -> list[Path]:
    return sorted(p for p in bundle.rglob("*.md") if p.is_file())


def concepts(bundle: Path):
    """Non-reserved markdown: everything but index.md / log.md."""
    for p in md_files(bundle):
        if p.name not in ("index.md", "log.md"):
            yield p, p.relative_to(bundle).as_posix()


# --- rule 1 (validator) + 5 + 12 -------------------------------------------

def run_validator(bundle: Path, f: Findings) -> None:
    r = okf.validate(bundle)
    for e in r.errors:
        f.err(1, "", e)
    for w in r.warnings:
        if LINK_WARN in w:
            f.warn(12, "", w)          # in-bundle links are WARN (rule 12)
        elif w.startswith("raw/"):
            # raw/ is human-written source material: `status: new|ingested`
            # lifecycle and missing `generated`/recommended fields are its
            # normal shape (template raw/CLAUDE.md), not agent errors.
            continue
        elif "matches no `sources[].id`" in w:
            f.err(5, "", w)
        else:
            f.err(1, "", w)            # --strict: warnings are errors


# --- per-file rules 2, 4, 6, 11, 14, 15 ------------------------------------

def check_files(bundle: Path, ticket_regex: str | None, f: Findings) -> None:
    today = datetime.date.today().isoformat()
    ticket_re = re.compile(ticket_regex) if ticket_regex else None
    for path, rel in concepts(bundle):
        if path.name == "CLAUDE.md":
            n = len(path.read_text(encoding="utf-8").splitlines())
            if n > CLAUDE_MD_MAX:
                f.err(6, rel, f"CLAUDE.md is {n} lines (max {CLAUDE_MD_MAX})")
        meta, body = load_meta(path)
        if not meta:
            continue  # rule 1 already flagged the missing frontmatter
        if meta.get("classification") not in CLASSIFICATIONS:
            f.err(2, rel, f"`classification` must be one of {sorted(CLASSIFICATIONS)} "
                          f"(got {meta.get('classification')!r})")
        if ticket_re is not None and "ticket" in meta:
            tickets = meta["ticket"] if isinstance(meta["ticket"], list) else [meta["ticket"]]
            for t in tickets:
                if not ticket_re.fullmatch(str(t)):
                    f.err(4, rel, f"`ticket` `{t}` does not match `{ticket_regex}`")
        stale = meta.get("stale_after")
        if stale is not None and str(stale) <= today:
            f.warn(15, rel, f"stale since {stale}")
        if path.name != "CLAUDE.md":  # guidance, not a concept page
            if rel.startswith("runbooks/"):
                check_runbook(meta, body, rel, f)
            if rel.startswith(("systems/", "runbooks/")):
                check_footnoted_paragraphs(body, rel, f)


def check_runbook(meta: dict, body: str, rel: str, f: Findings) -> None:
    for key in ("stale_after", "owners", "knows"):
        if not meta.get(key):
            f.err(11, rel, f"runbook frontmatter is missing `{key}`")
    h1s = [ln[2:].strip() for ln in body.splitlines() if ln.startswith("# ")]
    required = iter(RUNBOOK_HEADINGS)
    want = next(required)
    for h in h1s:
        if h == want:
            want = next(required, None)
            if want is None:
                return
    f.err(11, rel, f"runbook headings must include, in order: "
                   f"{', '.join(RUNBOOK_HEADINGS)} (missing from `{want}`)")


def check_footnoted_paragraphs(body: str, rel: str, f: Findings) -> None:
    # ponytail: naive block splitter — a "paragraph" is a blank-line-separated
    # run of non-fenced lines whose first line starts with a word character and
    # is not a footnote definition. Good enough for lint WARN; refine if noisy.
    in_fence = False
    block: list[str] = []
    blocks: list[list[str]] = []
    for ln in body.splitlines() + [""]:
        if okf.FENCE.match(ln.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if ln.strip():
            block.append(ln)
        elif block:
            blocks.append(block)
            block = []
    for lines in blocks:
        first = lines[0].lstrip()
        if not re.match(r"[A-Za-z]", first):  # skip lists, headings, tables, footnote defs
            continue
        if not any("[^" in ln for ln in lines):
            f.warn(14, rel, f"paragraph without a footnote: `{first[:60]}`")


# --- PR mode: rules 7, 8, 9, 10 --------------------------------------------

def git(bundle: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(bundle), *args],
                          capture_output=True, text=True, check=True).stdout


def check_pr(bundle: Path, base: str, bot: str | None, f: Findings) -> None:
    changed: dict[str, str] = {}  # path -> status letter
    for line in git(bundle, "diff", "--name-status", f"{base}...HEAD").splitlines():
        status, _, path = line.partition("\t")
        changed[path.split("\t")[-1]] = status[0]

    md_changed = {p: s for p, s in changed.items() if p.endswith(".md")}
    for path, status in md_changed.items():
        if path.startswith("raw/") and status in "MDR":
            try:
                base_text = git(bundle, "show", f"{base}:{path}")
            except subprocess.CalledProcessError:
                continue
            raw, _ = okf.split_frontmatter(base_text)
            meta = yaml.safe_load(raw) if raw else {}
            if isinstance(meta, dict) and meta.get("status") == "ingested":
                f.err(7, path, "raw/ file with `status: ingested` was modified")
        if status == "D" and not path.startswith("raw/"):
            f.err(9, path, "markdown deleted outside raw/; use `status: deprecated`")

    if bot:
        hits = git(bundle, "log", f"--author={bot}", "-G", "^verified:",
                   "--format=%h", f"{base}..HEAD").split()
        for sha in hits:
            f.err(8, sha, f"commit authored by `{bot}` changes a `verified:` line")

    concept_changed = [p for p in md_changed
                       if not p.startswith("raw/") and p not in ("index.md", "log.md")]
    if concept_changed:
        for reserved in ("index.md", "log.md"):
            if reserved not in changed:
                f.err(10, reserved, "concepts changed but this file was not touched")


# --- rule 13: cross-bundle links (--all mode) ------------------------------

def check_cross_links(root: Path, cfg: dict, f: Findings) -> None:
    ids = {b["id"] for b in cfg["bundles"]}
    host = re.escape(cfg["site_host"])
    link = re.compile(rf"^https?://{host}/([a-z0-9-]+)/(.+\.md)$")
    for b in cfg["bundles"]:
        bundle = root / b["id"]
        for path in md_files(bundle):
            rel = f"{b['id']}/{path.relative_to(bundle).as_posix()}"
            for target in okf.collect_link_targets(path):
                m = link.match(target.split("#", 1)[0])
                if not m:
                    continue
                other, sub = m.groups()
                if other not in ids:
                    f.warn(13, rel, f"link to unknown bundle `{other}`: {target}")
                elif not (root / other / sub).is_file():
                    f.warn(13, rel, f"cross-bundle target not found: {target}")


# --- entry ------------------------------------------------------------------

def lint_bundle(bundle: Path, ticket_regex: str | None, pr_base: str | None,
                bot: str | None, f: Findings) -> None:
    run_validator(bundle, f)
    check_files(bundle, ticket_regex, f)
    if pr_base:
        check_pr(bundle, pr_base, bot, f)


def main() -> int:
    ap = argparse.ArgumentParser(description="wiki-kit bundle lint (HANDOFF §6)")
    ap.add_argument("bundle", nargs="?", type=Path)
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    ap.add_argument("--ticket-regex", default=None)
    ap.add_argument("--pr", action="store_true")
    ap.add_argument("--base", default=None)
    ap.add_argument("--bot", default=None, help="bot author for rule 8")
    ap.add_argument("--all", action="store_true", dest="all_bundles")
    ap.add_argument("--bundles", type=Path, help="bundles.yml")
    ap.add_argument("--root", type=Path, default=Path("/bundles"))
    args = ap.parse_args()

    f = Findings()
    if args.all_bundles:
        if not args.bundles:
            ap.error("--all requires --bundles")
        cfg = yaml.safe_load(args.bundles.read_text())
        for b in cfg["bundles"]:
            lint_bundle(args.root / b["id"], b.get("ticket_regex"), None, None, f)
        check_cross_links(args.root, cfg, f)
    else:
        if not args.bundle:
            ap.error("bundle path required (or --all)")
        if args.pr and not args.base:
            ap.error("--pr requires --base")
        lint_bundle(args.bundle, args.ticket_regex,
                    args.base if args.pr else None, args.bot, f)

    for e in f.errors:
        print(f"ERROR {e}")
    for w in f.warnings:
        print(f"WARN  {w}")
    failed = bool(f.errors) or (args.strict and bool(f.warnings))
    print(f"lint: {len(f.errors)} error(s), {len(f.warnings)} warning(s)"
          + (" — FAIL" if failed else " — OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
