"""Tests for scripts/lint.py against the HANDOFF §6 rule table.

Static rules (1, 2, 4, 5, 6, 11, 12, 14, 15) run against tests/fixtures/.
PR-mode rules (7, 8, 9, 10) run against throwaway git repos seeded from
good-bundle. Rule 13 runs --all mode against a two-bundle root.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LINT = REPO / "scripts" / "lint.py"
GOOD = REPO / "tests" / "fixtures" / "good-bundle"
BAD = REPO / "tests" / "fixtures" / "bad-bundle"
TICKET_RE = r"^INC\d{7}$"


def lint(*args):
    return subprocess.run([sys.executable, str(LINT), *args],
                          capture_output=True, text=True)


# --- static rules -----------------------------------------------------------

def test_good_bundle_passes_strict():
    r = lint(str(GOOD), "--strict", "--ticket-regex", TICKET_RE)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.fixture(scope="module")
def bad_output():
    r = lint(str(BAD), "--ticket-regex", TICKET_RE)
    assert r.returncode == 1
    return r.stdout


@pytest.mark.parametrize("rule,fragment", [
    (1, "missing-frontmatter.md"),
    (2, "kitchen-sink.md"),
    (4, "BAD-1"),
    (5, "[^ghost]"),
    (6, "507 lines"),
    (11, "bad-runbook.md"),
])
def test_bad_bundle_errors(bad_output, rule, fragment):
    lines = [ln for ln in bad_output.splitlines()
             if ln.startswith("ERROR") and f"[rule {rule}]" in ln]
    assert lines, f"no rule {rule} error\n{bad_output}"
    assert any(fragment in ln for ln in lines)


@pytest.mark.parametrize("rule,fragment", [
    (12, "/systems/gone.md"),
    (14, "no-footnote.md"),
    (15, "stale since 2020-01-01"),
])
def test_bad_bundle_warnings(bad_output, rule, fragment):
    lines = [ln for ln in bad_output.splitlines()
             if ln.startswith("WARN") and f"[rule {rule}]" in ln]
    assert lines and any(fragment in ln for ln in lines), bad_output


# --- PR mode (rules 7-10) ---------------------------------------------------

def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                    "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path):
    dst = tmp_path / "bundle"
    shutil.copytree(GOOD, dst)
    git(dst, "init", "-b", "main")
    git(dst, "add", "-A")
    git(dst, "commit", "-m", "base")
    git(dst, "checkout", "-b", "pr")
    return dst


def commit_all(repo, msg, author=None):
    git(repo, "add", "-A")
    extra = ["--author", author] if author else []
    git(repo, "commit", "-m", msg, *extra)


def pr_lint(repo, *extra):
    return lint(str(repo), "--pr", "--base", "main", *extra)


def touch_index_log(repo):
    for name in ("index.md", "log.md"):
        p = repo / name
        p.write_text(p.read_text() + "\n<!-- touched -->\n")


def test_rule7_modifying_ingested_raw_fails(repo):
    p = repo / "raw/notes/2026-01-01-db-01-baseline.md"
    p.write_text(p.read_text() + "\nedited\n")
    commit_all(repo, "edit raw")
    r = pr_lint(repo)
    assert r.returncode == 1 and "[rule 7]" in r.stdout


def test_rule7_flipping_new_to_ingested_passes(repo):
    p = repo / "raw/notes/2026-01-02-new-note.md"
    p.write_text(p.read_text().replace("status: new", "status: ingested"))
    commit_all(repo, "flip status")
    r = pr_lint(repo)
    assert r.returncode == 0, r.stdout


def test_rule8_bot_touching_verified_fails(repo):
    p = repo / "systems/db-01.md"
    p.write_text(p.read_text().replace(
        "status: draft", "status: draft\nverified:\n  by: human:pat.db\n  at: \"2026-01-03\""))
    touch_index_log(repo)
    commit_all(repo, "verify", author="brainbot <bot@example.com>")
    r = pr_lint(repo, "--bot", "brainbot")
    assert r.returncode == 1 and "[rule 8]" in r.stdout
    # same diff, human author: rule 8 stays quiet
    r = lint(str(repo), "--pr", "--base", "main", "--bot", "someone-else")
    assert "[rule 8]" not in r.stdout


def test_rule9_deleting_md_outside_raw_fails(repo):
    git(repo, "rm", "runbooks/reboot-db-01.md")
    touch_index_log(repo)
    commit_all(repo, "delete runbook")
    r = pr_lint(repo)
    assert r.returncode == 1 and "[rule 9]" in r.stdout


def test_rule10_concept_change_without_index_log_fails(repo):
    p = repo / "systems/db-01.md"
    p.write_text(p.read_text() + "\nMore facts.[^db-01-baseline]\n")
    commit_all(repo, "edit concept only")
    r = pr_lint(repo)
    out = r.stdout
    assert r.returncode == 1
    assert sum("[rule 10]" in ln for ln in out.splitlines()) == 2  # index + log


def test_rule10_concept_change_with_index_log_passes(repo):
    p = repo / "systems/db-01.md"
    p.write_text(p.read_text() + "\nMore facts.[^db-01-baseline]\n")
    touch_index_log(repo)
    commit_all(repo, "edit concept + index + log")
    r = pr_lint(repo)
    assert r.returncode == 0, r.stdout


# --- rule 13: cross-bundle links (--all) ------------------------------------

def test_rule13_cross_bundle_links(tmp_path):
    root = tmp_path / "bundles"
    for bid in ("eng", "ops"):
        shutil.copytree(GOOD, root / bid)
    page = root / "eng" / "systems" / "db-01.md"
    page.write_text(page.read_text() + "\n".join([
        "", "# Cross links",
        "* [good](https://wiki.test/ops/systems/db-01.md)",
        "* [broken](https://wiki.test/ops/systems/missing.md)", "",
    ]))
    cfg = tmp_path / "bundles.yml"
    cfg.write_text(
        "site_host: wiki.test\n"
        "bundles:\n"
        "  - {id: eng, repo: x, path: /eng, branch: main, ticket_regex: '^INC\\d{7}$'}\n"
        "  - {id: ops, repo: x, path: /ops, branch: main, ticket_regex: '^INC\\d{7}$'}\n")
    r = lint("--all", "--bundles", str(cfg), "--root", str(root))
    assert r.returncode == 0, r.stdout  # warnings only
    warns = [ln for ln in r.stdout.splitlines() if "[rule 13]" in ln]
    assert len(warns) == 1 and "missing.md" in warns[0], r.stdout
