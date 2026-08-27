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
    n = html.escape(f.name)
    req = " required" if f.required else ""
    label = f"<label for=\"{n}\">{html.escape(f.label)}</label>"
    if f.type == "textarea":
        return f"{label}<textarea id=\"{n}\" name=\"{n}\"{req}>{v}</textarea>"
    if f.type == "select":
        opts = "".join(
            f"<option{' selected' if o == value else ''}>{html.escape(o)}</option>"
            for o in f.options)
        return f"{label}<select id=\"{n}\" name=\"{n}\"{req}>{opts}</select>"
    if f.type == "checkbox":
        checked = " checked" if value else ""
        return (f"{label}<input type=checkbox id=\"{n}\" name=\"{n}\""
                f"{checked}>")
    itype = "date" if f.type == "date" else "text"
    return (f"{label}<input type={itype} id=\"{n}\" name=\"{n}\" "
            f"value=\"{v}\"{req}>")


def render_form(*, form: config.Form, bundle_id: str, user: str,
                classification: str, ticket_regex: str | None,
                day: str = "", error: str | None = None,
                values: dict[str, str] | None = None) -> str:
    values = values or {}
    raw_kind = values.get("kind") or form.kinds[0]
    # An invalid kind (e.g. a rejected submission) has no directory to show
    # in the notice; fall back to the form's first allowed kind for display.
    kind = raw_kind if raw_kind in note.KIND_DIR else form.kinds[0]
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

    def reject(msg: str) -> Submission:
        return _reject(form, bundle_id, user, classification, ticket_regex,
                       values, day, msg)

    title = (values.get("title") or "").strip()
    if not title:
        return reject("A title is required.")

    kind = (values.get("kind") or form.kinds[0]).strip()
    if kind not in form.kinds:
        return reject(f"{kind!r} is not an allowed kind for this bundle.")

    for f in form.fields:
        value = (values.get(f.name) or "").strip()
        if f.required and not value:
            return reject(f"{f.label} is required.")
        # A POST need not come from the rendered <select>; pin it to the list.
        if f.type == "select" and value and value not in f.options:
            return reject(f"{value!r} is not an allowed value for {f.label}.")

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
    except Exception as exc:
        # Timeouts, DNS/TLS errors and unexpected response bodies all land
        # here: a 500 would throw away what the person just typed.
        detail = (str(exc) if isinstance(exc, github.GitHubError)
                  else type(exc).__name__)
        return reject(f"Could not file this right now: {detail}. "
                      "Your text is still here — try again in a minute.")

    done = (f"<h1>Filed</h1><p>Opened <a href='{html.escape(pr_url)}'>"
            f"{html.escape(pr_url)}</a>. It appears on the wiki once merged."
            f"</p>")
    return Submission(ok=True, html=_page("Filed", done), pr_url=pr_url)
