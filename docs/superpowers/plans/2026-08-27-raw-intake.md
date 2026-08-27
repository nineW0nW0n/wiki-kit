# Raw Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A browser form behind Cloudflare Access that turns a filled-in form into a correctly shaped `raw/` markdown file and opens a pull request against the bundle repo.

**Architecture:** A new `intake` container built from the existing image reads each bundle's `intake.yml` from the read-only `/bundles` mount, renders a server-side HTML form, and on submit calls the GitHub REST API to create a branch, add the file, and open a PR. `builder` and `mcp` keep their read-only mounts and credentials; `intake` holds the only write-scoped token. Request handling is split into pure functions with a thin ASGI wrapper, so unit tests need no HTTP client.

**Tech Stack:** Python 3.12, starlette + uvicorn + python-multipart + httpx2 (all already pulled in by `mcp==2.1.0`), Caddy, Docker Compose, pytest.

**Spec:** `docs/superpowers/specs/2026-08-27-raw-intake-design.md`

## Global Constraints

- **No new entries in `requirements.txt`.** Everything needed is a transitive dependency of `mcp==2.1.0`. HANDOFF §2 forbids unpinned or gratuitous dependencies.
- **No new test dependencies.** Unit tests call pure functions directly; HTTP-level behaviour is asserted in `tests/compose-test.sh`.
- **Reserved frontmatter keys:** `type`, `kind`, `author`, `date`, `classification`, `status`. An `intake.yml` field with one of these names is a hard error.
- **Field types:** `text`, `textarea`, `select`, `date`, `checkbox`. Nothing else.
- **Kinds:** `note`, `ticket`, `meeting`, `vendor`. These select the `raw/<kind>/` directory.
- **Filename format:** `raw/<kind>/<YYYY-MM-DD>-<slug>.md`. Slug is lowercase `[a-z0-9-]`, max 50 chars.
- **Frontmatter key order is fixed:** `type`, `kind`, `author`, `date`, `classification`, `ticket` (only when present), `status`. User-defined frontmatter fields follow, in `intake.yml` order.
- **Python style:** `from __future__ import annotations`, stdlib `argparse`, no type-checking dependencies. Match `scripts/lint.py` and `mcp/server.py`.
- **Commit style:** conventional commits, one per task minimum.
- Run all tests from the repo root. `pytest` is invoked as `python3 -m pytest`.

---

### Task 1: Shared bundle config loader

`mcp/server.py` already decides which bundles a caller may see. Intake needs the same decision. Extract it once so there is not a second authorization model to keep in sync.

**Files:**
- Create: `scripts/bundles.py`
- Modify: `mcp/server.py:21-42` (replace the local `_allowed` body with a call into the shared module)
- Test: `tests/test_bundles.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `load(path: Path) -> dict` — parse `bundles.yml`, return `{}` for an empty file, raise `OSError`/`yaml.YAMLError` on failure
  - `allowed_ids(cfg: dict, user: str) -> list[str]` — bundle ids visible to `user`; a bundle with no `readers:` key is visible to everyone, a bundle with `readers:` only to listed emails
  - `by_id(cfg: dict, bid: str) -> dict | None` — the bundle entry, or `None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_bundles.py`:

```python
"""Tests for scripts/bundles.py — the shared bundles.yml reader."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import bundles  # noqa: E402

CFG = {
    "site_host": "wiki.test",
    "bundles": [
        {"id": "eng", "repo": "https://github.com/o/brain-eng.git"},
        {"id": "hr", "repo": "https://github.com/o/brain-hr.git",
         "readers": ["alice@example.com"]},
    ],
}


def test_load_reads_yaml(tmp_path):
    p = tmp_path / "bundles.yml"
    p.write_text("site_host: wiki.test\nbundles: []\n", encoding="utf-8")
    assert bundles.load(p) == {"site_host": "wiki.test", "bundles": []}


def test_load_empty_file_is_empty_dict(tmp_path):
    p = tmp_path / "bundles.yml"
    p.write_text("", encoding="utf-8")
    assert bundles.load(p) == {}


def test_bundle_without_readers_is_public_to_authenticated_callers():
    assert "eng" in bundles.allowed_ids(CFG, "nobody@example.com")


def test_bundle_with_readers_is_restricted():
    assert bundles.allowed_ids(CFG, "nobody@example.com") == ["eng"]
    assert bundles.allowed_ids(CFG, "alice@example.com") == ["eng", "hr"]


def test_by_id_returns_entry_or_none():
    assert bundles.by_id(CFG, "eng")["repo"].endswith("brain-eng.git")
    assert bundles.by_id(CFG, "nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_bundles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bundles'`

- [ ] **Step 3: Write minimal implementation**

Create `scripts/bundles.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_bundles.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Point mcp/server.py at the shared module**

In `mcp/server.py`, add the scripts directory to the path next to the existing constants and replace the body of `_allowed`. The `import yaml` line stays — `_frontmatter` still uses it.

Replace lines 21-24 (the constants block) with:

```python
sys.path.insert(0, str(Path(os.environ.get("APP_DIR", "/app")) / "scripts"))
import bundles  # noqa: E402  (shared bundles.yml reader)

BUNDLES_FILE = Path(os.environ.get("BUNDLES_FILE", "/etc/wiki/bundles.yml"))
BUNDLES_DIR = Path(os.environ.get("BUNDLES_DIR", "/bundles"))
DB = Path(os.environ.get("STATE_DIR", "/state")) / "wiki.db"
PORT = int(os.environ.get("MCP_PORT", "8081"))
```

Add `import sys` to the import block at the top of the file.

Replace `_allowed` (lines 34-42) with:

```python
def _allowed(ctx: Context) -> list[str]:
    return bundles.allowed_ids(bundles.load(BUNDLES_FILE), _user(ctx))
```

- [ ] **Step 6: Verify mcp/server.py still parses and the old tests still pass**

Run: `python3 -c "import ast; ast.parse(open('mcp/server.py').read())" && python3 -m pytest tests/ -q`
Expected: no output from the parse check; all existing tests PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/bundles.py mcp/server.py tests/test_bundles.py
git commit -m "refactor: one reader for bundles.yml, shared by mcp and intake"
```

---

### Task 2: intake.yml parsing and validation

**Files:**
- Create: `intake/config.py`
- Test: `tests/test_intake_config.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `RESERVED: tuple[str, ...]`, `FIELD_TYPES: tuple[str, ...]`, `KINDS: tuple[str, ...]`
  - `class ConfigError(Exception)`
  - `class Field` with attributes `name, label, type, required, into, options`
  - `class Form` with attributes `title: str`, `kinds: list[str]`, `fields: list[Field]`
  - `load(bundle_dir: Path) -> Form` — returns the default form when `intake.yml` is absent; raises `ConfigError` with a human-readable message when present but invalid

- [ ] **Step 1: Write the failing test**

Create `tests/test_intake_config.py`:

```python
"""Tests for intake/config.py — intake.yml parsing and its refusals."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "intake"))

import config  # noqa: E402


def write(tmp_path: Path, text: str) -> Path:
    (tmp_path / "intake.yml").write_text(text, encoding="utf-8")
    return tmp_path


def test_missing_file_yields_default_form(tmp_path):
    form = config.load(tmp_path)
    assert [f.name for f in form.fields] == ["body"]
    assert form.fields[0].type == "textarea"
    assert form.kinds == list(config.KINDS)


def test_fields_are_parsed_in_order(tmp_path):
    d = write(tmp_path, """
title: "Drop a note"
fields:
  - name: summary
    label: "What happened?"
    type: textarea
    required: true
    into: body
  - name: system
    label: "Which system?"
    type: select
    options: [mail-01, db-01]
    into: frontmatter
""")
    form = config.load(d)
    assert form.title == "Drop a note"
    assert [f.name for f in form.fields] == ["summary", "system"]
    assert form.fields[0].required is True
    assert form.fields[1].options == ["mail-01", "db-01"]
    assert form.fields[1].into == "frontmatter"


def test_scalar_kind_pins_the_directory(tmp_path):
    d = write(tmp_path, "kind: meeting\nfields: []\n")
    assert config.load(d).kinds == ["meeting"]


def test_list_kind_limits_the_selector(tmp_path):
    d = write(tmp_path, "kind: [note, meeting]\nfields: []\n")
    assert config.load(d).kinds == ["note", "meeting"]


def test_unknown_kind_is_rejected(tmp_path):
    d = write(tmp_path, "kind: gossip\nfields: []\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert "gossip" in str(e.value)


@pytest.mark.parametrize("name", ["type", "kind", "author", "date",
                                  "classification", "status"])
def test_reserved_field_names_are_rejected(tmp_path, name):
    d = write(tmp_path, f"fields:\n  - name: {name}\n    label: X\n    type: text\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert name in str(e.value)
    assert "reserved" in str(e.value)


def test_unknown_field_type_is_rejected(tmp_path):
    d = write(tmp_path, "fields:\n  - name: x\n    label: X\n    type: colorpicker\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert "colorpicker" in str(e.value)


def test_select_without_options_is_rejected(tmp_path):
    d = write(tmp_path, "fields:\n  - name: x\n    label: X\n    type: select\n")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert "options" in str(e.value)


def test_malformed_yaml_is_a_config_error_not_a_traceback(tmp_path):
    d = write(tmp_path, "fields: [oh: no: yes\n")
    with pytest.raises(config.ConfigError):
        config.load(d)


def test_duplicate_field_names_are_rejected(tmp_path):
    d = write(tmp_path, """
fields:
  - name: x
    label: One
    type: text
  - name: x
    label: Two
    type: text
""")
    with pytest.raises(config.ConfigError) as e:
        config.load(d)
    assert "duplicate" in str(e.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_intake_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Write minimal implementation**

Create `intake/config.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_intake_config.py -v`
Expected: PASS, 15 tests (the reserved-name test is parametrized six ways)

- [ ] **Step 5: Commit**

```bash
git add intake/config.py tests/test_intake_config.py
git commit -m "feat: intake.yml schema, parsed with explicit refusals"
```

---

### Task 3: Note rendering, and the lint round-trip that proves it

This is the task that matters. Everything intake writes has to survive `scripts/lint.py --strict`, so the last test here generates a note into a copy of `fixtures/good-bundle` and lints it.

**Files:**
- Create: `intake/note.py`
- Test: `tests/test_intake_note.py`

**Interfaces:**
- Consumes: `intake/config.py` (`Field`, `Form`).
- Produces:
  - `slugify(title: str) -> str`
  - `author_from_email(email: str) -> str` — `"alice@corp.com"` becomes `"human:alice"`
  - `note_path(kind: str, day: str, slug: str) -> str` — `raw/<kind>/<day>-<slug>.md`
  - `render(*, title: str, kind: str, author: str, day: str, classification: str, ticket: str | None, form: Form, values: dict[str, str]) -> str` — the complete file text

- [ ] **Step 1: Write the failing test**

Create `tests/test_intake_note.py`:

```python
"""Tests for intake/note.py — slug, frontmatter, body, and a lint round-trip."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "intake"))

import config  # noqa: E402
import note  # noqa: E402

GOOD = REPO / "tests" / "fixtures" / "good-bundle"
LINT = REPO / "scripts" / "lint.py"


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
    assert "ticket: INC0001234" in with_ticket
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
    assert text.index("status:") < text.index("system: mail-01")


def test_generated_note_passes_lint_strict(tmp_path):
    """The one that matters: intake output must satisfy the §6 rules."""
    bundle = tmp_path / "eng"
    shutil.copytree(GOOD, bundle)
    form = config.Form(title="t", kinds=["note"], fields=[
        config.Field(name="what", label="What happened?", type="textarea",
                     into="body"),
    ])
    text = note.render(title="Disk filled up", kind="note",
                       author="human:alice", day="2026-08-27",
                       classification="P1", ticket=None, form=form,
                       values={"what": "df said 100%."})
    target = bundle / note.note_path("note", "2026-08-27", "disk-filled-up")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

    r = subprocess.run([sys.executable, str(LINT), str(bundle), "--strict"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_intake_note.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'note'`

- [ ] **Step 3: Write minimal implementation**

Create `intake/note.py`:

```python
#!/usr/bin/env python3
"""note.py — turn form values into a raw/ file.

Shape is fixed by template/raw/CLAUDE.md: no `title` key (the title is the
H1), `kind` selects the directory, and the key order below is the documented
one. Filenames are YYYY-MM-DD-<slug>.md; anything else is a lint error the
human would have to fix, which is the whole point of generating it here.
"""
from __future__ import annotations

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
        lines.append(f"ticket: {ticket}")
    lines.append("status: new")
    for f in form.fields:
        value = (values.get(f.name) or "").strip()
        if f.into == "frontmatter" and value:
            lines.append(f"{f.name}: {value}")
    lines += ["---", "", f"# {title}", ""]
    for f in form.fields:
        value = (values.get(f.name) or "").strip()
        if f.into == "body" and value:
            lines += [f"## {f.label}", "", value, ""]
    return "\n".join(lines).rstrip("\n") + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_intake_note.py -v`
Expected: PASS. If `test_generated_note_passes_lint_strict` fails, read the `[rule N]` tag in the captured output and fix `render` — never the fixture or the linter.

- [ ] **Step 5: Commit**

```bash
git add intake/note.py tests/test_intake_note.py
git commit -m "feat: render raw/ notes from form values, lint-verified"
```

---

### Task 4: GitHub client

**Files:**
- Create: `intake/github.py`
- Test: `tests/test_intake_github.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `class GitHubError(Exception)` with attribute `status: int`
  - `owner_repo(url: str) -> tuple[str, str]` — accepts `https://github.com/o/brain-eng.git` and `git@github.com:o/brain-eng.git`
  - `open_note_pr(*, request, token, url, base, path, content, title, body, day, slug) -> str` — returns the PR's HTML URL. `request(method, path, token, json)` is injected so tests never touch the network; it returns `(status: int, payload: dict)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_intake_github.py`:

```python
"""Tests for intake/github.py with an injected fake transport."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "intake"))

import github  # noqa: E402


class Fake:
    """Records calls; replays a scripted list of (status, payload)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, method, path, token, json=None):
        self.calls.append((method, path, json))
        return self.script.pop(0)


OK_REF = (200, {"object": {"sha": "basesha"}})
OK_CREATED = (201, {})
OK_PR = (201, {"html_url": "https://github.com/o/brain-eng/pull/7"})


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/o/brain-eng.git", ("o", "brain-eng")),
    ("https://github.com/o/brain-eng", ("o", "brain-eng")),
    ("git@github.com:o/brain-eng.git", ("o", "brain-eng")),
])
def test_owner_repo(url, expected):
    assert github.owner_repo(url) == expected


def test_happy_path_makes_four_calls_and_returns_the_pr_url():
    fake = Fake([OK_REF, OK_CREATED, OK_CREATED, OK_PR])
    pr = github.open_note_pr(
        request=fake, token="t", url="https://github.com/o/brain-eng.git",
        base="main", path="raw/notes/2026-08-27-x.md", content="hello",
        title="x", body="filed by alice", day="2026-08-27", slug="x")
    assert pr == "https://github.com/o/brain-eng/pull/7"
    assert [c[0] for c in fake.calls] == ["GET", "POST", "PUT", "POST"]
    assert fake.calls[1][2]["ref"] == "refs/heads/intake/2026-08-27-x"


def test_existing_path_retries_with_a_suffix():
    # PUT 422 means the path exists; the next PUT should carry -2.
    fake = Fake([OK_REF, OK_CREATED, (422, {}), OK_CREATED, OK_PR])
    github.open_note_pr(
        request=fake, token="t", url="https://github.com/o/brain-eng.git",
        base="main", path="raw/notes/2026-08-27-x.md", content="hello",
        title="x", body="b", day="2026-08-27", slug="x")
    puts = [c[1] for c in fake.calls if c[0] == "PUT"]
    assert puts[0].endswith("2026-08-27-x.md")
    assert puts[1].endswith("2026-08-27-x-2.md")


def test_gives_up_after_five_collisions():
    fake = Fake([OK_REF, OK_CREATED] + [(422, {})] * 5 + [(204, {})])
    with pytest.raises(github.GitHubError) as e:
        github.open_note_pr(
            request=fake, token="t", url="https://github.com/o/brain-eng.git",
            base="main", path="raw/notes/2026-08-27-x.md", content="hello",
            title="x", body="b", day="2026-08-27", slug="x")
    assert "already exists" in str(e.value)


def test_failed_put_deletes_the_branch_it_created():
    fake = Fake([OK_REF, OK_CREATED, (500, {}), (204, {})])
    with pytest.raises(github.GitHubError):
        github.open_note_pr(
            request=fake, token="t", url="https://github.com/o/brain-eng.git",
            base="main", path="raw/notes/2026-08-27-x.md", content="hello",
            title="x", body="b", day="2026-08-27", slug="x")
    assert fake.calls[-1][0] == "DELETE"
    assert fake.calls[-1][1].endswith("refs/heads/intake/2026-08-27-x")


def test_expired_token_surfaces_as_401():
    fake = Fake([(401, {"message": "Bad credentials"})])
    with pytest.raises(github.GitHubError) as e:
        github.open_note_pr(
            request=fake, token="t", url="https://github.com/o/brain-eng.git",
            base="main", path="raw/notes/2026-08-27-x.md", content="hello",
            title="x", body="b", day="2026-08-27", slug="x")
    assert e.value.status == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_intake_github.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'github'`

- [ ] **Step 3: Write minimal implementation**

Create `intake/github.py`:

```python
#!/usr/bin/env python3
"""github.py — branch, file, pull request. Nothing else.

The transport is injected so tests never reach the network, and so the only
credentialed call site in the service is `_http` below. A contents PUT without
a `sha` fails with 422 when the path exists; that is the collision check, so
no extra probe call is made.
"""
from __future__ import annotations

import base64
import os
import re

MAX_SUFFIX = 5


class GitHubError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def owner_repo(url: str) -> tuple[str, str]:
    m = re.search(r"[/:]([^/:]+)/([^/]+?)(?:\.git)?$", url.strip())
    if not m:
        raise GitHubError(f"cannot read owner/repo from {url!r}")
    return m.group(1), m.group(2)


def _suffixed(path: str, n: int) -> str:
    return path[:-3] + f"-{n}.md" if n > 1 else path


def open_note_pr(*, request, token: str, url: str, base: str, path: str,
                 content: str, title: str, body: str, day: str,
                 slug: str) -> str:
    owner, repo = owner_repo(url)
    api = f"repos/{owner}/{repo}"
    branch = f"intake/{day}-{slug}"

    status, payload = request("GET", f"{api}/git/ref/heads/{base}", token, None)
    if status != 200:
        raise GitHubError(f"cannot read {base}: HTTP {status}", status)
    base_sha = payload["object"]["sha"]

    status, _ = request("POST", f"{api}/git/refs", token,
                        {"ref": f"refs/heads/{branch}", "sha": base_sha})
    if status not in (200, 201):
        raise GitHubError(f"cannot create branch {branch}: HTTP {status}", status)

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    written = None
    for n in range(1, MAX_SUFFIX + 1):
        candidate = _suffixed(path, n)
        status, _ = request("PUT", f"{api}/contents/{candidate}", token,
                            {"message": f"raw: {title}", "content": encoded,
                             "branch": branch})
        if status in (200, 201):
            written = candidate
            break
        if status != 422:
            _delete_branch(request, token, api, branch)
            raise GitHubError(f"cannot write {candidate}: HTTP {status}", status)
    if written is None:
        _delete_branch(request, token, api, branch)
        raise GitHubError(f"{path} and {MAX_SUFFIX - 1} suffixed variants "
                          f"already exists; rename the note", 422)

    status, payload = request("POST", f"{api}/pulls", token,
                              {"title": f"raw: {title}", "head": branch,
                               "base": base, "body": body})
    if status not in (200, 201):
        _delete_branch(request, token, api, branch)
        raise GitHubError(f"file written but PR failed: HTTP {status}", status)
    return payload["html_url"]


def _delete_branch(request, token: str, api: str, branch: str) -> None:
    try:
        request("DELETE", f"{api}/git/refs/heads/{branch}", token, None)
    except Exception:  # best effort; the caller already has a real error
        pass


def http(method: str, path: str, token: str, json=None):
    """Real transport. Imported lazily so unit tests need no HTTP client."""
    import httpx2 as httpx

    base = os.environ.get("GITHUB_API", "https://api.github.com")
    r = httpx.request(
        method, f"{base}/{path}", timeout=15.0,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
        json=json)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_intake_github.py -v`
Expected: PASS, 8 tests

- [x] **Step 5: RESOLVED — the real transport's import name**

`mcp==2.1.0` depends on `httpx2>=2.5.0`. Confirmed against the published wheel
(`httpx2-2.5.0-py3-none-any.whl`): the package installs a single top-level module named
`httpx2` and exports `request` from its `__init__`. So `import httpx2 as httpx` followed by
`httpx.request(...)` is correct as written, and no image build is needed to check it. Nothing
is added to `requirements.txt` — `httpx2` arrives as a transitive dependency of `mcp`.

- [ ] **Step 6: Commit**

```bash
git add intake/github.py tests/test_intake_github.py
git commit -m "feat: intake GitHub client — branch, file, PR, with rollback"
```

---

### Task 5: Form rendering, submit handling, and the ASGI wrapper

Handlers are pure functions taking plain dicts, so they are unit-testable without an HTTP client. `app.py` is the thin starlette shell around them.

**Files:**
- Create: `intake/handlers.py`
- Create: `intake/app.py`
- Test: `tests/test_intake_handlers.py`

**Interfaces:**
- Consumes: in `handlers.py` — `config.Form`, `config.Field`, `note.render`, `note.slugify`, `note.author_from_email`, `note.note_path`, `github.open_note_pr`, `github.GitHubError`. In `app.py` additionally — `bundles.load`, `bundles.allowed_ids`, `bundles.by_id`, `config.load`, `config.ConfigError`, `github.http`.
- Produces:
  - `render_form(*, form, bundle_id, user, classification, ticket_regex, error=None, values=None) -> str` — complete HTML page including the notice block
  - `class Submission` with attributes `ok: bool`, `html: str`, `pr_url: str | None`
  - `handle_submit(*, form, bundle, bundle_id, user, values, day, dry_run, request, token) -> Submission`

- [ ] **Step 1: Write the failing test**

Create `tests/test_intake_handlers.py`:

```python
"""Tests for intake/handlers.py — the pure request handlers."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "intake"))
sys.path.insert(0, str(REPO / "scripts"))

import config  # noqa: E402
import handlers  # noqa: E402

FORM = config.Form(title="Drop a note", kinds=["note"], fields=[
    config.Field(name="what", label="What happened?", type="textarea",
                 required=True, into="body"),
])
BUNDLE = {"id": "eng", "repo": "https://github.com/o/brain-eng.git",
          "branch": "main", "ticket_regex": r"^INC\d{7}$"}


def render(**kw):
    base = dict(form=FORM, bundle_id="eng", user="alice@corp.com",
                classification="P1", ticket_regex=r"^INC\d{7}$")
    base.update(kw)
    return handlers.render_form(**base)


def test_notice_block_shows_the_real_frontmatter():
    html = render()
    for line in ["type: Source", "kind: note", "author: human:alice",
                 "classification: P1", "status: new"]:
        assert line in html


def test_notice_block_lists_every_reserved_name():
    html = render()
    for name in config.RESERVED:
        assert name in html


def test_notice_block_shows_the_target_path_with_a_slug_placeholder():
    assert "raw/notes/" in render()
    assert "&lt;slug&gt;" in render()


def test_user_values_are_escaped_not_injected():
    html = render(values={"what": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_required_field_missing_is_refused_before_any_api_call():
    calls = []
    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "Outage", "kind": "note", "what": ""},
        day="2026-08-27", dry_run=False,
        request=lambda *a, **k: calls.append(a) or (200, {}), token="t")
    assert result.ok is False
    assert "What happened?" in result.html
    assert calls == []


def test_missing_title_is_refused():
    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "", "kind": "note", "what": "x"},
        day="2026-08-27", dry_run=True, request=None, token="t")
    assert result.ok is False


def test_bad_ticket_is_refused_before_any_api_call():
    calls = []
    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "T", "kind": "note", "what": "x", "ticket": "nope"},
        day="2026-08-27", dry_run=False,
        request=lambda *a, **k: calls.append(a) or (200, {}), token="t")
    assert result.ok is False
    assert "INC" in result.html
    assert calls == []


def test_unknown_kind_is_refused():
    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "T", "kind": "gossip", "what": "x"},
        day="2026-08-27", dry_run=True, request=None, token="t")
    assert result.ok is False


def test_dry_run_previews_the_file_and_calls_nothing():
    calls = []
    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "Disk filled", "kind": "note", "what": "df said 100%"},
        day="2026-08-27", dry_run=True,
        request=lambda *a, **k: calls.append(a) or (200, {}), token="t")
    assert result.ok is True
    assert result.pr_url is None
    assert "raw/notes/2026-08-27-disk-filled.md" in result.html
    assert "df said 100%" in result.html
    assert calls == []


def test_oversized_body_is_refused():
    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "T", "kind": "note", "what": "x" * (handlers.MAX_BYTES + 1)},
        day="2026-08-27", dry_run=True, request=None, token="t")
    assert result.ok is False
    assert "too large" in result.html


def test_successful_submit_returns_the_pr_url():
    script = [(200, {"object": {"sha": "s"}}), (201, {}), (201, {}),
              (201, {"html_url": "https://github.com/o/brain-eng/pull/3"})]

    def request(method, path, token, json=None):
        return script.pop(0)

    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "Disk filled", "kind": "note", "what": "df"},
        day="2026-08-27", dry_run=False, request=request, token="t")
    assert result.ok is True
    assert result.pr_url == "https://github.com/o/brain-eng/pull/3"


def test_api_failure_keeps_the_typed_values_in_the_form():
    def request(method, path, token, json=None):
        return (500, {})

    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "Disk filled", "kind": "note",
                "what": "a long incident write-up"},
        day="2026-08-27", dry_run=False, request=request, token="t")
    assert result.ok is False
    assert "a long incident write-up" in result.html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_intake_handlers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'handlers'`

- [ ] **Step 3: Write minimal implementation**

Create `intake/handlers.py`:

```python
#!/usr/bin/env python3
"""handlers.py — pure request handling. No ASGI types cross this boundary.

Everything here takes plain dicts and returns strings, so the whole submit
path is unit-testable without an HTTP client. app.py is the shell.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

import config
import github
import note

MAX_BYTES = 512 * 1024

CSS = """
body{font:16px/1.6 system-ui;max-width:46rem;margin:2rem auto;padding:0 1rem;
color:#222;background:#fff}
@media(prefers-color-scheme:dark){body{color:#eee;background:#161618}
pre,.notice{background:#222}}
label{display:block;margin:1.2rem 0 .3rem;font-weight:600}
input,textarea,select{width:100%;padding:.5rem;font:inherit;box-sizing:border-box}
textarea{min-height:9rem}
.notice{background:#f4f4f5;padding:1rem;border-left:3px solid #888;
font:13px/1.5 ui-monospace,monospace;white-space:pre-wrap;overflow-x:auto}
.error{border-left-color:#c00;color:#c00}
button{margin-top:1.5rem;padding:.6rem 1.4rem;font:inherit}
"""


@dataclass
class Submission:
    ok: bool
    html: str
    pr_url: str | None = None


def _page(title: str, inner: str) -> str:
    return (f"<!doctype html><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style>{inner}")


def _notice(bundle_id: str, kind: str, user: str, classification: str,
            day: str, ticket_regex: str | None) -> str:
    fm = "\n".join([
        f"This will be committed as {note.note_path(kind, day, '<slug>')}",
        "", "---", "type: Source", f"kind: {kind}",
        f"author: {note.author_from_email(user)}", f"date: {day}",
        f"classification: {classification}", "status: new", "---", "",
        "Reserved — cannot be used as field names in intake.yml:",
        "  " + "   ".join(config.RESERVED),
    ])
    if ticket_regex:
        fm += f"\n\nticket is allowed, and must match {ticket_regex}"
    return f"<div class=notice>{html.escape(fm)}</div>"


def _input(f: config.Field, value: str) -> str:
    v = html.escape(value or "")
    req = " required" if f.required else ""
    label = f"<label for={f.name}>{html.escape(f.label)}</label>"
    if f.type == "textarea":
        return f"{label}<textarea id={f.name} name={f.name}{req}>{v}</textarea>"
    if f.type == "select":
        opts = "".join(
            f"<option{' selected' if o == value else ''}>{html.escape(o)}</option>"
            for o in f.options)
        return f"{label}<select id={f.name} name={f.name}{req}>{opts}</select>"
    if f.type == "checkbox":
        checked = " checked" if value else ""
        return (f"{label}<input type=checkbox id={f.name} name={f.name}"
                f"{checked}>")
    itype = "date" if f.type == "date" else "text"
    return (f"{label}<input type={itype} id={f.name} name={f.name} "
            f"value=\"{v}\"{req}>")


def render_form(*, form: config.Form, bundle_id: str, user: str,
                classification: str, ticket_regex: str | None,
                day: str = "", error: str | None = None,
                values: dict[str, str] | None = None) -> str:
    values = values or {}
    kind = values.get("kind") or form.kinds[0]
    parts = [f"<h1>{html.escape(form.title)}</h1>",
             f"<p>Filing into <strong>{html.escape(bundle_id)}</strong> "
             f"as {html.escape(note.author_from_email(user))}.</p>",
             _notice(bundle_id, kind, user, classification, day or "today",
                     ticket_regex)]
    if error:
        parts.append(f"<div class='notice error'>{html.escape(error)}</div>")
    parts.append(f"<form method=post action='/intake/{html.escape(bundle_id)}'>")
    parts.append("<label for=title>Title</label>"
                 f"<input id=title name=title required "
                 f"value=\"{html.escape(values.get('title', ''))}\">")
    if len(form.kinds) > 1:
        opts = "".join(
            f"<option{' selected' if k == kind else ''}>{k}</option>"
            for k in form.kinds)
        parts.append(f"<label for=kind>Kind</label>"
                     f"<select id=kind name=kind>{opts}</select>")
    else:
        parts.append(f"<input type=hidden name=kind value={form.kinds[0]}>")
    if ticket_regex:
        parts.append("<label for=ticket>Ticket (optional)</label>"
                     f"<input id=ticket name=ticket "
                     f"value=\"{html.escape(values.get('ticket', ''))}\">")
    for f in form.fields:
        parts.append(_input(f, values.get(f.name, "")))
    parts.append("<button type=submit>Submit</button></form>")
    return _page(form.title, "".join(parts))


def _reject(form, bundle_id, user, classification, ticket_regex, values, day,
            message) -> Submission:
    return Submission(ok=False, html=render_form(
        form=form, bundle_id=bundle_id, user=user,
        classification=classification, ticket_regex=ticket_regex, day=day,
        error=message, values=values))


def handle_submit(*, form: config.Form, bundle: dict, bundle_id: str,
                  user: str, values: dict[str, str], day: str, dry_run: bool,
                  request, token: str) -> Submission:
    classification = str(bundle.get("tier", "P1"))
    ticket_regex = bundle.get("ticket_regex")
    reject = lambda msg: _reject(form, bundle_id, user, classification,  # noqa: E731
                                 ticket_regex, values, day, msg)

    title = (values.get("title") or "").strip()
    if not title:
        return reject("A title is required.")

    kind = (values.get("kind") or form.kinds[0]).strip()
    if kind not in form.kinds:
        return reject(f"{kind!r} is not an allowed kind for this bundle.")

    for f in form.fields:
        if f.required and not (values.get(f.name) or "").strip():
            return reject(f"{f.label} is required.")

    ticket = (values.get("ticket") or "").strip() or None
    if ticket and ticket_regex and not re.fullmatch(ticket_regex, ticket):
        return reject(f"Ticket {ticket!r} does not match {ticket_regex}.")

    text = note.render(title=title, kind=kind,
                       author=note.author_from_email(user), day=day,
                       classification=classification, ticket=ticket,
                       form=form, values=values)
    if len(text.encode("utf-8")) > MAX_BYTES:
        return reject("That note is too large to file through the form "
                      f"(limit {MAX_BYTES // 1024} KB).")

    slug = note.slugify(title)
    path = note.note_path(kind, day, slug)
    if dry_run:
        preview = (f"<h1>Preview</h1><p>Nothing was filed — this service is "
                   f"in dry-run mode.</p><p><code>{html.escape(path)}</code>"
                   f"</p><pre class=notice>{html.escape(text)}</pre>")
        return Submission(ok=True, html=_page("Preview", preview))

    try:
        pr_url = github.open_note_pr(
            request=request, token=token, url=bundle["repo"],
            base=bundle.get("branch", "main"), path=path, content=text,
            title=title, body=f"Filed from the wiki intake form by {user}.",
            day=day, slug=slug)
    except github.GitHubError as exc:
        return reject(f"Could not file this right now: {exc}. "
                      "Your text is still here — try again in a minute.")

    done = (f"<h1>Filed</h1><p>Opened <a href='{html.escape(pr_url)}'>"
            f"{html.escape(pr_url)}</a>. It appears on the wiki once merged."
            f"</p>")
    return Submission(ok=True, html=_page("Filed", done), pr_url=pr_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_intake_handlers.py -v`
Expected: PASS, 12 tests

- [ ] **Step 5: Write the ASGI shell**

Create `intake/app.py`:

```python
#!/usr/bin/env python3
"""app.py — the intake service.

Reachable only through Caddy's :8090 tunnel listener, which strips any
client-supplied X-Wiki-User and rewrites it from Cloudflare Access. An empty
X-Wiki-User is refused: `author: human:<id>` needs a human, and HANDOFF §9
records that service tokens carry no email.
"""
from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(os.environ.get("APP_DIR", "/app")) / "scripts"))

import bundles  # noqa: E402
import config  # noqa: E402
import github  # noqa: E402
import handlers  # noqa: E402

BUNDLES_FILE = Path(os.environ.get("BUNDLES_FILE", "/etc/wiki/bundles.yml"))
BUNDLES_DIR = Path(os.environ.get("BUNDLES_DIR", "/bundles"))
PORT = int(os.environ.get("INTAKE_PORT", "8082"))
DRY_RUN = os.environ.get("INTAKE_DRY_RUN", "1") != "0"
TOKEN = os.environ.get("INTAKE_TOKEN", "")


def _user(request) -> str:
    return request.headers.get("x-wiki-user", "").strip()


def _today() -> str:
    return datetime.date.today().isoformat()


def _forbidden(message: str) -> HTMLResponse:
    return HTMLResponse(f"<h1>Not allowed</h1><p>{message}</p>", status_code=403)


async def index(request):
    user = _user(request)
    if not user:
        return _forbidden("This form needs a signed-in person, not a service "
                          "token.")
    cfg = bundles.load(BUNDLES_FILE)
    ids = [b for b in bundles.allowed_ids(cfg, user)
           if (BUNDLES_DIR / b).is_dir()]
    if not ids:
        return HTMLResponse("<h1>Nothing to file into</h1><p>Your account has "
                            "no bundle it may write to. Ask the wiki owner.</p>")
    links = "".join(f"<li><a href='/intake/{b}'>{b}</a></li>" for b in ids)
    return HTMLResponse(f"<h1>Add to the wiki</h1><ul>{links}</ul>")


def _load(bundle_id: str, user: str):
    cfg = bundles.load(BUNDLES_FILE)
    if bundle_id not in bundles.allowed_ids(cfg, user):
        return None, None
    return bundles.by_id(cfg, bundle_id), config.load(BUNDLES_DIR / bundle_id)


async def form(request):
    user = _user(request)
    if not user:
        return _forbidden("This form needs a signed-in person.")
    bundle_id = request.path_params["bundle"]
    try:
        bundle, form_cfg = _load(bundle_id, user)
    except config.ConfigError as exc:
        return HTMLResponse(f"<h1>{bundle_id} cannot accept submissions</h1>"
                            f"<p>Its intake.yml is invalid: {exc}</p>",
                            status_code=500)
    if bundle is None:
        return _forbidden(f"No bundle {bundle_id!r} you may write to.")
    return HTMLResponse(handlers.render_form(
        form=form_cfg, bundle_id=bundle_id, user=user,
        classification=str(bundle.get("tier", "P1")),
        ticket_regex=bundle.get("ticket_regex"), day=_today()))


async def submit(request):
    user = _user(request)
    if not user:
        return _forbidden("This form needs a signed-in person.")
    if request.headers.get("sec-fetch-site", "same-origin") != "same-origin":
        return _forbidden("Cross-site submissions are refused.")
    bundle_id = request.path_params["bundle"]
    try:
        bundle, form_cfg = _load(bundle_id, user)
    except config.ConfigError as exc:
        return HTMLResponse(f"<h1>Invalid intake.yml</h1><p>{exc}</p>",
                            status_code=500)
    if bundle is None:
        return _forbidden(f"No bundle {bundle_id!r} you may write to.")
    values = {k: str(v) for k, v in (await request.form()).items()}
    result = handlers.handle_submit(
        form=form_cfg, bundle=bundle, bundle_id=bundle_id, user=user,
        values=values, day=_today(), dry_run=DRY_RUN, request=github.http,
        token=TOKEN)
    return HTMLResponse(result.html, status_code=200 if result.ok else 400)


async def health(request):
    if not TOKEN:
        return JSONResponse({"intake": "no-token"})
    try:
        status, _ = github.http("GET", "rate_limit", TOKEN, None)
    except Exception:
        return JSONResponse({"intake": "unreachable"})
    if status == 401:
        return JSONResponse({"intake": "expired"})
    return JSONResponse({"intake": "ok" if status == 200 else f"http-{status}"})


app = Starlette(routes=[
    Route("/intake", index),
    Route("/intake/", index),
    Route("/health", health),
    Route("/intake/{bundle}", form, methods=["GET"]),
    Route("/intake/{bundle}", submit, methods=["POST"]),
])

if __name__ == "__main__":
    # Fail at boot, not on someone's first submission (matches the builder).
    if not BUNDLES_FILE.is_file():
        raise SystemExit(f"no bundles file at {BUNDLES_FILE}")
    bundles.load(BUNDLES_FILE)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

- [ ] **Step 6: Verify the module imports cleanly**

Run: `python3 -c "import ast; [ast.parse(open(p).read()) for p in ('intake/app.py','intake/handlers.py')]" && python3 -m pytest tests/ -q`
Expected: parse check silent; all tests PASS. `app.py` cannot be imported outside the image (starlette is not installed locally) — that is what the compose test in Task 6 is for.

- [ ] **Step 7: Commit**

```bash
git add intake/handlers.py intake/app.py tests/test_intake_handlers.py
git commit -m "feat: intake form rendering and submit handling"
```

---

### Task 6: Wire it into the image, Caddy and compose

**Files:**
- Modify: `Dockerfile:30-34` (copy `intake/`)
- Modify: `entrypoint.sh:131-136` (add the `intake` subcommand)
- Modify: `Caddyfile:32-49` (route `/intake*` on `:8090`, refuse on `:8080`)
- Modify: `docker-compose.yml:30-37` (add the `intake` service)
- Modify: `tests/compose-test.sh:66-72` (assert both routes)

**Interfaces:**
- Consumes: `intake/app.py` from Task 5.
- Produces: the `intake` service on `:8082` inside the compose network; `/intake*` served on Caddy's `:8090` only.

- [ ] **Step 1: Add intake to the image**

In `Dockerfile`, after the `COPY mcp/ mcp/` line, add:

```dockerfile
COPY intake/ intake/
```

- [ ] **Step 2: Add the entrypoint subcommand**

In `entrypoint.sh`, in the `case "$cmd"` block, add a line before the `*)` catch-all:

```sh
    intake)   exec python3 "$APP/intake/app.py" ;;
```

Also add `intake` to the usage comment at the top of the file:

```sh
#   intake                       intake web form (HANDOFF §8)
```

- [ ] **Step 3: Route it in Caddy**

In `Caddyfile`, inside the `:8080` block, extend the existing refusal so intake is refused there too:

```caddyfile
	handle /mcp* {
		respond "MCP is served through the tunnel only" 403
	}

	handle /intake* {
		respond "The intake form is served through the tunnel only" 403
	}
```

Inside the `:8090` block, after the existing `/mcp*` handler, add:

```caddyfile
	handle /intake* {
		reverse_proxy intake:8082 {
			header_up -X-Wiki-User
			header_up X-Wiki-User {header.Cf-Access-Authenticated-User-Email}
		}
	}
```

- [ ] **Step 4: Add the compose service**

In `docker-compose.yml`, after the `mcp` service, add:

```yaml
  intake:
    build: .
    command: ["intake"]
    environment:
      INTAKE_TOKEN: "${INTAKE_TOKEN:-}"
      INTAKE_DRY_RUN: "${INTAKE_DRY_RUN:-1}"
    volumes:
      - "${BUNDLES_YML:-./bundles.yml}:/etc/wiki/bundles.yml:ro"
      - bundles:/bundles:ro
    restart: unless-stopped
```

Note there is no `/site` and no `/state` mount: intake reads bundles and writes only through the GitHub API.

- [ ] **Step 5: Assert both routes in the compose test**

In `tests/compose-test.sh`, after the existing `/mcp` 403 assertion, add:

```sh
echo "== intake refused on the published port, served on the tunnel port"
code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/intake)
[ "$code" = 403 ] || { echo "FAIL: /intake on :8080 returned $code, want 403"; exit 1; }

docker compose -f "$REPO/docker-compose.yml" -f "$SEED/override.yml" \
    exec -T web wget -qO- \
    --header="Cf-Access-Authenticated-User-Email: alice@test" \
    http://localhost:8090/intake | grep -q "Add to the wiki" || {
    echo "FAIL: /intake on :8090 did not render the bundle list"; exit 1; }
```

- [ ] **Step 6: Fold intake health into status.json**

The spec requires token expiry to be visible on `/status` rather than discovered by
a frustrated colleague. In `entrypoint.sh`, inside `run_loop`, replace the line that
starts the status writer so the intake health answer is fetched first:

```sh
        intake_health=$(python3 -c "
import json, urllib.request
try:
    with urllib.request.urlopen('http://intake:8082/health', timeout=5) as r:
        print(json.load(r).get('intake', 'unknown'))
except Exception:
    print('unreachable')
" 2>/dev/null || echo unreachable)

        python3 - "$results" "$STATE_DIR/status.json" "$SITE_DIR/index.html" \
                 "$intake_health" <<'EOF'
```

Then in the embedded python that writes `status.json`, add the key:

```python
status = {"updated": updated,
          "intake": sys.argv[4],
          "bundles": {r[0]: {"sha": r[1], "lint_exit": int(r[2]), "build": r[3]}
                      for r in rows}}
```

`urllib.request` is stdlib, so the builder gains no dependency and no token: it reads
a health verdict the intake service already computed.

- [ ] **Step 7: Run the full smoke and compose tests**

Run: `bash tests/smoke.sh && bash tests/compose-test.sh`
Expected: both print `OK`. The intake service starts in dry-run mode with no token, which is correct for this step. `/status` should now carry `"intake": "no-token"`.

- [ ] **Step 8: Commit**

```bash
git add Dockerfile entrypoint.sh Caddyfile docker-compose.yml tests/compose-test.sh
git commit -m "feat: intake service in the image, behind the tunnel listener"
```

---

### Task 7: Node provisioning, template default, and going live

**Files:**
- Modify: `scripts/deploy_wizard.sh` (three new stages; bump `TOTAL_STAGES`)
- Create: `template/intake.yml`
- Modify: `bundles.example.yml` (document the `tier:` key intake reads)
- Modify: `CLAUDE.md` (one line under Commands)

**Interfaces:**
- Consumes: everything above.
- Produces: a deployed, non-dry-run intake service.

- [ ] **Step 1: Ship a default intake.yml with the template**

Create `template/intake.yml`:

```yaml
---
# Fields shown on the wiki's intake form for this bundle.
# Adding a field here is a commit — no deploy, no node access. It appears on
# the form within one builder cycle.
#
# type: text | textarea | select | date | checkbox
# into: body (a ## section) | frontmatter (a key)
# Reserved names, generated for you: type, kind, author, date,
# classification, status. `ticket` is yours but must match the bundle regex.
title: "Add to {{BUNDLE_ID}}"
kind: [note, meeting, ticket]
fields:
  - name: what
    label: "What happened, in your own words?"
    type: textarea
    required: true
    into: body
  - name: system
    label: "Which system is this about? (optional)"
    type: text
    into: frontmatter
```

- [ ] **Step 2: Verify the template still lints**

Run: `python3 scripts/okf_validate.py template --strict && python3 -m pytest tests/ -q`
Expected: both pass. `intake.yml` is not markdown, so the validator ignores it; if a §6 rule trips on it, that is a real finding — report it rather than deleting the file.

- [ ] **Step 3: Document the tier key**

In `bundles.example.yml`, add to the `eng` entry:

```yaml
    # tier: classification stamped on notes filed through the intake form
    tier: P1
```

- [ ] **Step 4: Add the wizard stages**

In `scripts/deploy_wizard.sh`, change `TOTAL_STAGES=8` to `TOTAL_STAGES=11`, and add these three stages after the existing stage 6 (the Access service token stage):

```bash
# ── 7 ─────────────────────────────────────────────────────────────────────
stage "Intake token (write-scoped, separate from the pull token)"
say "The intake form opens PRs. That needs its own fine-grained PAT."
open_url "https://github.com/settings/personal-access-tokens/new"
step "Token name: wiki-kit-intake · Expiration: your call."
step "Repository access: Only select repositories → every brain-* repo."
step "NEVER include wiki-kit itself."
step "Permissions → Repository → Contents: Read and write."
step "Permissions → Repository → Pull requests: Read and write."
step "Nothing else. Generate, then copy the token."
ask_secret INTAKE_TOKEN "Paste the intake PAT:"
write_env INTAKE_TOKEN "$INTAKE_TOKEN"

# ── 8 ─────────────────────────────────────────────────────────────────────
stage "Branch protection (this is what stops the token reaching main)"
say "The intake token can push branches. Protection is what keeps it off main."
for_each_repo="your brain-* repos"
step "For each of $for_each_repo, open Settings → Branches → Add rule."
step "Branch name pattern: main"
step "Tick: Require a pull request before merging."
warn "Without this rule the intake token can write straight to main."
pause "Protection enabled on every brain-* repo? Press Enter."

# ── 9 ─────────────────────────────────────────────────────────────────────
stage "Access policy for /intake"
say "Reading the wiki and filing into it should be grantable separately."
open_url "https://one.dash.cloudflare.com/"
step "Access → Applications → Add an application → Self-hosted."
step "Name: wiki-intake · Domain: $SITE_HOST · Path: intake"
step "Policy 'filers': Action Allow · Include → the people who may file."
pause "Application saved? Press Enter."
```

Renumber the two existing final stages to 10 and 11.

- [ ] **Step 5: Check the wizard still parses**

Run: `bash -n scripts/deploy_wizard.sh`
Expected: no output.

- [ ] **Step 6: Turn dry-run off on the node**

This step runs on the node, not in the repo. In the deploy directory's `.env`:

```sh
INTAKE_DRY_RUN=0
```

Then: `docker compose --profile tunnel up -d --build intake`

Verify: `curl -fsS http://localhost:8080/status | grep intake` shows `"intake": "ok"`. If it shows `expired`, the PAT is wrong or already expired; if `no-token`, `INTAKE_TOKEN` did not reach the container.

- [ ] **Step 7: End-to-end check with a real person**

Ask a colleague who does not use git to open `https://<site_host>/intake`, file one note, and confirm a PR appears on the bundle repo. That is the acceptance criterion for the whole plan — not a passing test suite.

- [ ] **Step 8: Document the commands**

In `CLAUDE.md`, under the Commands block, add:

```sh
python3 -m pytest tests/ -q                         # all tests, including intake
docker run --rm -e INTAKE_DRY_RUN=1 wiki-kit intake # intake service, writes nothing
```

- [ ] **Step 9: Commit**

```bash
git add scripts/deploy_wizard.sh template/intake.yml bundles.example.yml CLAUDE.md
git commit -m "feat: provision intake on the node; default intake.yml in template"
```
