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


def test_receipt_shows_the_real_frontmatter():
    html = render()
    for key, value in [("type", "Source"), ("kind", "note"),
                       ("author", "human:alice"), ("classification", "P1"),
                       ("status", "new")]:
        assert f"<dt>{key}</dt><dd>{value}</dd>" in html


def test_receipt_accounts_for_every_reserved_name():
    """RESERVED and the receipt must not drift: each generated key is shown."""
    html = render()
    for name in config.RESERVED:
        assert f"<dt>{name}</dt>" in html


def test_receipt_does_not_lecture_the_submitter_about_intake_yml():
    """Reserved-name guidance is for the bundle owner, not the person filing."""
    assert "cannot be used as field names" not in render()


def test_receipt_shows_the_target_path_with_a_slug_placeholder():
    assert "raw/notes/" in render()
    assert "&lt;slug&gt;" in render()


def test_ticket_pattern_is_shown_beside_the_field_it_constrains():
    assert "INC" in render().split("name=ticket", 1)[1].split("</p>", 1)[0]


def test_user_values_are_escaped_not_injected():
    html = render(values={"what": "<script>alert(1)</script>"})
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_user_values_cannot_break_out_of_an_attribute():
    payload = '" onmouseover=alert(1) x="'
    html = render(values={"title": payload})
    assert '" onmouseover=alert(1)' not in html
    assert "&quot; onmouseover=alert(1)" in html


def test_field_name_from_intake_yml_is_escaped_in_attributes():
    form = config.Form(title="t", kinds=["note"], fields=[
        config.Field(name='x" autofocus onfocus=alert(1)', label="X",
                     type="text", required=False, into="body"),
    ])
    html = render(form=form)
    assert 'x" autofocus' not in html
    assert "x&quot; autofocus" in html


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
    assert "does not match" in result.html
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


def test_select_value_outside_its_options_is_refused_before_any_api_call():
    calls = []
    form = config.Form(title="t", kinds=["note"], fields=[
        config.Field(name="system", label="System", type="select",
                     required=True, into="frontmatter",
                     options=["mail-01", "db-01"]),
    ])
    result = handlers.handle_submit(
        form=form, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "T", "kind": "note",
                "system": "mail-01\nclassification: P3"},
        day="2026-08-27", dry_run=False,
        request=lambda *a, **k: calls.append(a) or (200, {}), token="t")
    assert result.ok is False
    assert "not an allowed value" in result.html
    assert calls == []


def test_transport_exception_keeps_the_typed_values_in_the_form():
    """A timeout or a malformed body must not become a 500 that eats the note."""
    def request(method, path, token, json=None):
        raise TimeoutError("connect timed out")

    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "Disk filled", "kind": "note",
                "what": "a long incident write-up"},
        day="2026-08-27", dry_run=False, request=request, token="t")
    assert result.ok is False
    assert "a long incident write-up" in result.html
    assert "TimeoutError" in result.html
    assert "connect timed out" not in result.html


def test_unexpected_response_body_is_caught_not_raised():
    def request(method, path, token, json=None):
        return (200, {})  # no ["object"]["sha"]

    result = handlers.handle_submit(
        form=FORM, bundle=BUNDLE, bundle_id="eng", user="alice@corp.com",
        values={"title": "Disk filled", "kind": "note", "what": "df"},
        day="2026-08-27", dry_run=False, request=request, token="t")
    assert result.ok is False
    assert "KeyError" in result.html


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
