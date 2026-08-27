"""Tests for intake/note.py — slug, frontmatter, body, and a lint round-trip."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "intake"))

import config  # noqa: E402
import note  # noqa: E402

GOOD = REPO / "tests" / "fixtures" / "good-bundle"
LINT = REPO / "scripts" / "lint.py"


def frontmatter(text: str) -> dict:
    return yaml.safe_load(text.split("---\n")[1])


@pytest.mark.parametrize("title,expected", [
    ("Mail server fell over", "mail-server-fell-over"),
    ("  Spaces   collapse  ", "spaces-collapse"),
    ("Slashes/and:colons", "slashes-and-colons"),
    ("MiXeD CaSe", "mixed-case"),
    ("", "note"),
    ("🔥🔥🔥", "note"),
    ("a" * 80, "a" * 50),
])
def test_slugify(title, expected):
    assert note.slugify(title) == expected


def test_author_from_email_takes_the_local_part():
    assert note.author_from_email("alice@corp.com") == "human:alice"


def test_note_path_follows_the_raw_layout_rule():
    assert note.note_path("meeting", "2026-08-27", "standup") == \
        "raw/meetings/2026-08-27-standup.md"
    assert note.note_path("note", "2026-08-27", "x") == "raw/notes/2026-08-27-x.md"


def test_frontmatter_key_order_matches_raw_claude_md():
    form = config.Form(title="t", kinds=["note"], fields=[])
    text = note.render(title="A thing", kind="note", author="human:alice",
                       day="2026-08-27", classification="P1", ticket=None,
                       form=form, values={})
    keys = [ln.split(":", 1)[0] for ln in text.splitlines()[1:]
            if ln and not ln.startswith("---")]
    assert keys[:5] == ["type", "kind", "author", "date", "classification"]
    assert keys[5] == "status"


def test_ticket_is_written_only_when_given():
    form = config.Form(title="t", kinds=["note"], fields=[])
    without = note.render(title="T", kind="note", author="human:a",
                          day="2026-08-27", classification="P1", ticket=None,
                          form=form, values={})
    assert "ticket:" not in without
    with_ticket = note.render(title="T", kind="note", author="human:a",
                              day="2026-08-27", classification="P1",
                              ticket="INC0001234", form=form, values={})
    assert frontmatter(with_ticket)["ticket"] == "INC0001234"
    assert with_ticket.index("ticket:") < with_ticket.index("status:")


def test_body_fields_become_sections_and_empties_are_dropped():
    form = config.Form(title="t", kinds=["note"], fields=[
        config.Field(name="what", label="What happened?", type="textarea",
                     into="body"),
        config.Field(name="impact", label="Impact", type="text", into="body"),
    ])
    text = note.render(title="Outage", kind="note", author="human:a",
                       day="2026-08-27", classification="P1", ticket=None,
                       form=form, values={"what": "It fell over", "impact": ""})
    assert "# Outage" in text
    assert "## What happened?\n\nIt fell over" in text
    assert "## Impact" not in text


def test_frontmatter_fields_are_appended_after_generated_keys():
    form = config.Form(title="t", kinds=["note"], fields=[
        config.Field(name="system", label="System", type="select",
                     into="frontmatter", options=["mail-01"]),
    ])
    text = note.render(title="T", kind="note", author="human:a",
                       day="2026-08-27", classification="P1", ticket=None,
                       form=form, values={"system": "mail-01"})
    assert text.index("status:") < text.index("system:")
    assert frontmatter(text)["system"] == "mail-01"


FM_FORM = config.Form(title="t", kinds=["note"], fields=[
    config.Field(name="system", label="System", type="text",
                 into="frontmatter"),
])


@pytest.mark.parametrize("value", [
    "Ticket ref: 12345",                        # a colon breaks bare YAML
    "mail-01\nclassification: P3\nstatus: ingested",  # forged reserved keys
    "# not a comment",
    'he said "no"',
    "  ",                                       # strips to empty; key dropped
    "back\\slash and \ttab",
    "unicodé — em dash",
])
def test_frontmatter_values_cannot_forge_keys_or_break_yaml(value):
    text = note.render(title="T", kind="note", author="human:a",
                       day="2026-08-27", classification="P1", ticket=None,
                       form=FM_FORM, values={"system": value})
    meta = frontmatter(text)
    assert meta["classification"] == "P1"
    assert meta["status"] == "new"
    assert meta.get("system") == (value.strip() or None)


def test_generated_note_passes_lint_strict(tmp_path):
    """The one that matters: intake output must satisfy the §6 rules."""
    bundle = tmp_path / "eng"
    shutil.copytree(GOOD, bundle)
    form = config.Form(title="t", kinds=["note"], fields=[
        config.Field(name="what", label="What happened?", type="textarea",
                     into="body"),
        # template/intake.yml ships an `into: frontmatter` field, so the
        # round-trip has to cover one — with a value that is hostile to YAML.
        config.Field(name="system", label="System", type="text",
                     into="frontmatter"),
    ])
    text = note.render(title="Disk filled up", kind="note",
                       author="human:alice", day="2026-08-27",
                       classification="P1", ticket=None, form=form,
                       values={"what": "df said 100%.",
                               "system": "Ticket ref: 12345\nstatus: ingested"})
    target = bundle / note.note_path("note", "2026-08-27", "disk-filled-up")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

    r = subprocess.run([sys.executable, str(LINT), str(bundle), "--strict"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    meta = frontmatter(target.read_text(encoding="utf-8"))
    assert meta["status"] == "new"
    assert meta["classification"] == "P1"
