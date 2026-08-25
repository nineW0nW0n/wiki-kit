#!/bin/sh
# build_site.sh <bundle-id> — render one bundle to $SITE_DIR/<id> (HANDOFF §7).
# Env: SITE_HOST (required), QUARTZ_DIR=/opt/quartz, BUNDLES_DIR=/bundles,
#      SITE_DIR=/site, CONFIG_TEMPLATE=<next to this script>.
set -eu

ID="$1"
SITE_HOST="${SITE_HOST:?SITE_HOST is required}"
QUARTZ_DIR="${QUARTZ_DIR:-/opt/quartz}"
BUNDLES_DIR="${BUNDLES_DIR:-/bundles}"
SITE_DIR="${SITE_DIR:-/site}"
CONFIG_TEMPLATE="${CONFIG_TEMPLATE:-$(dirname "$0")/quartz.config.template.yaml}"

[ -d "$BUNDLES_DIR/$ID" ] || { echo "no bundle at $BUNDLES_DIR/$ID" >&2; exit 1; }

# Symlink, never copy: copying breaks the Explorer folder tree (HANDOFF §7).
rm -rf "$QUARTZ_DIR/content"
ln -s "$BUNDLES_DIR/$ID" "$QUARTZ_DIR/content"

sed -e "s|@BASE_URL@|$SITE_HOST/$ID|g" -e "s|@PAGE_TITLE@|$ID|g" \
    "$CONFIG_TEMPLATE" > "$QUARTZ_DIR/quartz.config.yaml"

mkdir -p "$SITE_DIR"
(cd "$QUARTZ_DIR" && npx quartz build -o "$SITE_DIR/.$ID.new")

# Atomic swap: rename in, old tree removed after.
rm -rf "$SITE_DIR/.$ID.old"
[ -e "$SITE_DIR/$ID" ] && mv "$SITE_DIR/$ID" "$SITE_DIR/.$ID.old"
mv "$SITE_DIR/.$ID.new" "$SITE_DIR/$ID"
rm -rf "$SITE_DIR/.$ID.old"

echo "built $SITE_DIR/$ID (baseUrl $SITE_HOST/$ID)"
