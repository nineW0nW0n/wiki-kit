#!/bin/sh
# Step-6 acceptance (HANDOFF §11): docker compose up; curl :8080/eng/ is HTML;
# curl :8080/eng/index.md is raw markdown. Seeds a local bare repo from
# template/ so no network or token is needed.
set -eu

cd "$(dirname "$0")/.."
REPO="$PWD"
SEED="$(mktemp -d)"
trap 'docker compose -f "$REPO/docker-compose.yml" down -v --remove-orphans >/dev/null 2>&1 || true; rm -rf "$SEED"' EXIT

echo "== seed bare repo from template/"
cp -R template "$SEED/eng-src"
git -C "$SEED/eng-src" init -q -b main
git -C "$SEED/eng-src" -c user.name=seed -c user.email=seed@test add -A
git -C "$SEED/eng-src" -c user.name=seed -c user.email=seed@test commit -qm seed
git clone -q --bare "$SEED/eng-src" "$SEED/eng.git"

cat > "$SEED/bundles.yml" <<'EOF'
site_host: wiki.test
interval_seconds: 60
bundles:
  - id: eng
    repo: file:///seed/eng.git
    path: /eng
    branch: main
EOF

cat > "$SEED/override.yml" <<EOF
services:
  builder:
    volumes:
      - $SEED/eng.git:/seed/eng.git:ro
EOF

echo "== compose up"
export BUNDLES_YML="$SEED/bundles.yml"
docker compose -f "$REPO/docker-compose.yml" -f "$SEED/override.yml" up -d --build

echo "== wait for first build cycle"
tries=0
until curl -fs http://localhost:8080/eng/ | grep -qi "<html"; do
    tries=$((tries + 1))
    [ "$tries" -gt 60 ] && {
        echo "FAIL: /eng/ not serving HTML"; docker compose logs builder | tail -40; exit 1; }
    sleep 5
done
echo "html ok"

echo "== raw markdown route"
curl -fs http://localhost:8080/eng/index.md | grep -q "okf_version" || {
    echo "FAIL: /eng/index.md is not the raw bundle file"; exit 1; }
curl -fs http://localhost:8080/eng/systems/mail-01.md | grep -q "type: System" || {
    echo "FAIL: /eng/systems/mail-01.md is not raw markdown"; exit 1; }

echo "== status + generated artifacts"
curl -fs http://localhost:8080/status | grep -q '"eng"' || {
    echo "FAIL: /status missing bundle"; exit 1; }
curl -fs http://localhost:8080/eng/cited-by-other-domains.md >/dev/null || {
    echo "FAIL: cited-by page missing"; exit 1; }
curl -fs http://localhost:8080/eng/index.md | grep -q "Single Point of Failure" || {
    echo "FAIL: SPOF section missing from index.md"; exit 1; }
curl -fs http://localhost:8080/eng/viz.html | grep -qi "<html" || {
    echo "FAIL: viz.html missing"; exit 1; }

echo "== compose-test: OK"
