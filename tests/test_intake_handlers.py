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
