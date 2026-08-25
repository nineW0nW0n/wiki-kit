#!/bin/sh
# Smoke test: build the image, lint the shipped template bundle, verify FTS5.
# Usage: tests/smoke.sh [image-tag]   (default: wiki-kit:smoke)
set -eu

IMG="${1:-wiki-kit:smoke}"
cd "$(dirname "$0")/.."

echo "== docker build"
docker build -t "$IMG" .

echo "== lint template (strict validator + §6 rules)"
docker run --rm "$IMG" lint /app/template --strict

echo "== validate template (vendored validator, strict)"
docker run --rm "$IMG" validate /app/template --strict

echo "== VERIFY sqlite FTS5 (HANDOFF §11 step 4)"
docker run --rm "$IMG" python3 -c \
    "import sqlite3; sqlite3.connect(':memory:').execute('create virtual table t using fts5(x)'); print('fts5 ok')"

echo "== build site for template bundle as 'eng' (HANDOFF §11 step 5)"
docker run --rm -e SITE_HOST=wiki.test "$IMG" sh -c '
    set -eu
    mkdir -p /bundles /site
    cp -R /app/template /bundles/eng
    /app/scripts/build_site.sh eng
    pages=$(find /site/eng -name "*.html" | wc -l)
    echo "html pages: $pages"
    [ "$pages" -ge 3 ] || { echo "FAIL: expected >= 3 pages"; exit 1; }
    for p in systems/mail-01 runbooks/restart-mail-01 concepts/backup-strategy; do
        [ -f "/site/eng/$p.html" ] || { echo "FAIL: missing $p.html"; exit 1; }
    done
    # VERIFY (step 5): internal links are relative (subpath-safe) — no
    # root-absolute hrefs that would escape /eng behind Caddy...
    if grep -o "href=\"/[^\"]*\"" /site/eng/index.html \
            /site/eng/systems/mail-01.html | grep -v "href=\"/eng"; then
        echo "FAIL: root-absolute href escapes the /eng subpath"; exit 1
    fi
    # ...and absolute URLs (sitemap) honor the baseUrl subpath.
    grep -q "<loc>https://wiki.test/eng/" /site/eng/sitemap.xml || {
        echo "FAIL: sitemap does not carry the /eng subpath"; exit 1; }
    echo "subpath links ok"
'

echo "== smoke: OK"
