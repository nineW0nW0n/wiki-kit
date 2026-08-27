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
