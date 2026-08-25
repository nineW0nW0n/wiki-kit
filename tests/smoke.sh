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

echo "== smoke: OK"
