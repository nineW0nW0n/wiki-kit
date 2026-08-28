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
:root{color-scheme:light dark;
--bg:#fbfbfa;--surface:#fff;--sunken:#f4f4f2;
--text:#1c1c1a;--muted:#63635e;--line:#e2e2dd;--line-strong:#c9c9c2;
--accent:#3d5a3d;--accent-text:#fff;--accent-weak:#eef2ee;
--danger:#a02020;--danger-weak:#fbeeee;--ok:#2c5c3a;--ok-weak:#eef4ef;
--s1:.25rem;--s2:.5rem;--s3:.75rem;--s4:1rem;--s5:1.5rem;--s6:2rem;
--radius:6px;--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{
--bg:#141416;--surface:#1b1b1e;--sunken:#232327;
--text:#e8e8e4;--muted:#a0a09a;--line:#2e2e33;--line-strong:#43434a;
--accent:#9dc49d;--accent-text:#14170f;--accent-weak:#1f2620;
--danger:#f08a8a;--danger-weak:#2a1a1a;--ok:#8fc9a4;--ok-weak:#18231c}}
*{box-sizing:border-box}
body{margin:0;padding:var(--s5) var(--s4) var(--s6);font:16px/1.6 var(--sans);
color:var(--text);background:var(--bg);-webkit-text-size-adjust:100%}
main{max-width:44rem;margin:0 auto}
h1{font-size:1.5rem;line-height:1.25;margin:0 0 var(--s2);letter-spacing:-.01em}
p{margin:0 0 var(--s4)}
a{color:inherit;text-underline-offset:3px}
code{font-family:var(--mono)}
.lede{color:var(--muted);margin-bottom:var(--s5)}
.lede strong{color:var(--text)}
.receipt{border:1px solid var(--line);border-radius:var(--radius);
background:var(--surface);margin:0 0 var(--s5);overflow:hidden}
.receipt-head{display:flex;flex-wrap:wrap;gap:var(--s1) var(--s3);
align-items:baseline;padding:var(--s3) var(--s4);background:var(--sunken);
border-bottom:1px solid var(--line)}
.receipt-head b{font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;
color:var(--muted);font-weight:600}
.receipt-head code{font-size:.85rem;line-height:1.5;word-break:break-all}
.receipt-body{display:grid;grid-template-columns:max-content 1fr;
gap:var(--s1) var(--s4);padding:var(--s4);margin:0;
font:.85rem/1.6 var(--mono)}
.receipt-body dt{color:var(--muted)}
.receipt-body dd{margin:0;word-break:break-word}
.receipt-note{padding:var(--s3) var(--s4);border-top:1px solid var(--line);
font-size:.8rem;color:var(--muted);margin:0}
form{margin:0}
label{display:block;margin:var(--s5) 0 var(--s2);font-weight:600;line-height:1.4}
label .opt{font-weight:400;color:var(--muted)}
input[type=text],input[type=date],textarea,select{width:100%;
padding:.55rem .7rem;font:inherit;color:var(--text);background:var(--surface);
border:1px solid var(--line-strong);border-radius:var(--radius);appearance:none}
select{padding-right:2.2rem;background-repeat:no-repeat;
background-size:5px 5px,5px 5px;
background-position:calc(100% - 18px) 55%,calc(100% - 13px) 55%;
background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),
linear-gradient(135deg,var(--muted) 50%,transparent 50%)}
textarea{min-height:11rem;resize:vertical;line-height:1.6}
input[type=checkbox]{width:1.1rem;height:1.1rem;accent-color:var(--accent)}
:is(input,textarea,select):hover{border-color:var(--muted)}
:is(input,textarea,select,button,a):focus-visible{outline:2px solid var(--accent);
outline-offset:2px}
.hint{margin:var(--s1) 0 0;font-size:.85rem;color:var(--muted)}
button{margin-top:var(--s6);padding:.6rem 1.5rem;font:inherit;font-weight:600;
color:var(--accent-text);background:var(--accent);border:1px solid transparent;
border-radius:var(--radius);cursor:pointer}
button:hover{filter:brightness(1.08)}
.alert{display:flex;gap:var(--s3);padding:var(--s3) var(--s4);margin:0 0 var(--s5);
border:1px solid var(--line);border-left:4px solid var(--line-strong);
border-radius:var(--radius);background:var(--sunken)}
.alert svg{flex:none;width:1.15rem;height:1.15rem;margin-top:.2rem}
.alert p{margin:0}
.alert p+p{margin-top:var(--s1);color:var(--muted);font-size:.9rem}
.alert-error{border-left-color:var(--danger);background:var(--danger-weak)}
.alert-error strong{color:var(--danger)}
.alert-ok{border-left-color:var(--ok);background:var(--ok-weak)}
pre{margin:0 0 var(--s5);padding:var(--s4);overflow-x:auto;
font:.85rem/1.6 var(--mono);background:var(--sunken);
border:1px solid var(--line);border-radius:var(--radius)}
.bundles{list-style:none;margin:0;padding:0}
.bundles li+li{margin-top:var(--s2)}
.bundles a{display:block;padding:var(--s3) var(--s4);text-decoration:none;
border:1px solid var(--line);border-radius:var(--radius);background:var(--surface)}
.bundles a:hover{border-color:var(--accent);background:var(--accent-weak)}
.prlink{word-break:break-all;font-family:var(--mono);font-size:.9rem}
@media(max-width:30rem){.receipt-body{grid-template-columns:1fr;gap:0}
.receipt-body dt{margin-top:var(--s2)}button{width:100%}}
"""

# Inline because the container serves no static assets: Caddy routes /intake*
# to this app and nothing else, so there is nowhere an <img> or icon file
# could be fetched from.
ICONS = {
    "error": "<path d='M10 1.8 19 18H1Z'/><path d='M10 7.5v4.2'/>"
             "<path d='M10 14.4v.2'/>",
    "info": "<circle cx='10' cy='10' r='8.2'/><path d='M10 9v5'/>"
            "<path d='M10 6v.4'/>",
    "ok": "<path d='M4 10.5 8 14.5 16 6'/>",
}


@dataclass
class Submission:
    ok: bool
    html: str
    pr_url: str | None = None


def page(title: str, inner: str) -> str:
    """The shell every screen shares. app.py's own pages go through it too."""
    return (f"<!doctype html><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style>"
            f"<main>{inner}</main>")


def alert(kind: str, message: str, detail: str = "", *,
          strong: bool = False) -> str:
    """One-line status block. `kind` is error, info or ok."""
    body = f"<strong>{message}</strong>" if strong else message
    parts = [f"<p>{body}</p>"]
    if detail:
        parts.append(f"<p>{detail}</p>")
    role = " role=alert tabindex=-1" if kind == "error" else ""
    return (f"<div class='alert alert-{kind}'{role}>"
            f"<svg viewBox='0 0 20 20' aria-hidden=true fill=none "
            f"stroke=currentColor stroke-width=1.6 stroke-linecap=round "
            f"stroke-linejoin=round>{ICONS[kind]}</svg>"
            f"<div>{''.join(parts)}</div></div>")


def _receipt(kind: str, user: str, classification: str, day: str) -> str:
    """What will be committed, and the keys filled in on the submitter's behalf.

    The values are the same constants note.render() writes, in the same order,
    so the page cannot promise a file shape the writer does not produce. The
    reserved-name list that used to live here is configuration guidance for the
    bundle owner, not for the person filing a note; it belongs in intake.yml's
    comments, where it also is.
    """
    generated = [("type", "Source"), ("kind", kind),
                 ("author", note.author_from_email(user)), ("date", day),
                 ("classification", classification), ("status", "new")]
    rows = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>"
                   for k, v in generated)
    path = html.escape(note.note_path(kind, day, "<slug>"))
    return (f"<div class=receipt><div class=receipt-head>"
            f"<b>Will be committed as</b><code>{path}</code></div>"
            f"<dl class=receipt-body>{rows}</dl>"
            f"<p class=receipt-note>Filled in for you. "
            f"<code>&lt;slug&gt;</code> comes from the title.</p></div>")


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
             f"<p class=lede>Filing into <strong>{html.escape(bundle_id)}</strong> "
             f"as {html.escape(note.author_from_email(user))}.</p>"]
    if error:
        # Before the receipt: a rejected submitter needs the reason and the
        # reassurance first, not the filing metadata.
        parts.append(alert("error", html.escape(error),
                           "Nothing was filed. Everything you typed is still "
                           "below.", strong=True))
    parts.append(_receipt(kind, user, classification, day or "today"))
    parts.append(f"<form method=post action='/intake/{html.escape(bundle_id)}'>")
    parts.append("<label for=title>Title</label>"
                 f"<input type=text id=title name=title required "
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
        # The pattern moves next to the field it constrains; lint rule 4 would
        # otherwise reject the pull request where nobody who typed it will look.
        parts.append("<label for=ticket>Ticket <span class=opt>(optional)"
                     "</span></label>"
                     f"<input type=text id=ticket name=ticket "
                     f"value=\"{html.escape(values.get('ticket', ''))}\">"
                     f"<p class=hint>Must match "
                     f"<code>{html.escape(ticket_regex)}</code></p>")
    for f in form.fields:
        parts.append(_input(f, values.get(f.name, "")))
    parts.append("<button type=submit>Submit</button></form>")
    return page(form.title, "".join(parts))


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
        preview = (f"<h1>Preview</h1>"
                   + alert("info", "Nothing was filed — this service is in "
                                   "dry-run mode.")
                   + f"<p class=lede><code>{html.escape(path)}</code></p>"
                   + f"<pre>{html.escape(text)}</pre>")
        return Submission(ok=True, html=page("Preview", preview))

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

    link = (f"Opened <a class=prlink href='{html.escape(pr_url)}'>"
            f"{html.escape(pr_url)}</a>")
    done = (f"<h1>Filed</h1>"
            + alert("ok", link, "It appears on the wiki once merged."))
    return Submission(ok=True, html=page("Filed", done), pr_url=pr_url)
