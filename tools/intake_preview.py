#!/usr/bin/env python3
"""intake_preview.py — render an intake form to a file, without Docker.

`handlers.render_form` is pure, so the whole visual surface can be checked from
a checkout: no container, no network, no GitHub token. Only for looking at the
form while designing it; the tests are what pin its behaviour.

    python3 scripts/intake_preview.py
    python3 scripts/intake_preview.py --bundle-dir tests/fixtures/good-bundle
    python3 scripts/intake_preview.py --error "Ticket 'X' does not match ..."
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "intake"))

import config  # noqa: E402
import handlers  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle-dir", default="template",
                    help="directory holding intake.yml (default: template)")
    ap.add_argument("--bundle-id", default="work")
    ap.add_argument("--user", default="you@example.com")
    ap.add_argument("--classification", default="P1")
    ap.add_argument("--ticket-regex", default=r"^(OPS|INC)-\d+$",
                    help="empty string hides the ticket field")
    ap.add_argument("--day", default="2026-08-28")
    ap.add_argument("--error", default=None,
                    help="render the rejected state with this message")
    ap.add_argument("--out", default=str(pathlib.Path(tempfile.gettempdir())
                                         / "intake-preview.html"))
    args = ap.parse_args()

    form = config.load(pathlib.Path(args.bundle_dir))
    page = handlers.render_form(
        form=form, bundle_id=args.bundle_id, user=args.user,
        classification=args.classification,
        ticket_regex=args.ticket_regex or None, day=args.day,
        error=args.error,
        # A rejected submission re-renders with what was typed; show that.
        values={"title": "Mail server fell over"} if args.error else None)
    out = pathlib.Path(args.out)
    out.write_text(page)
    print(out)


if __name__ == "__main__":
    main()
