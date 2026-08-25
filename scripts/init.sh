#!/bin/sh
# init.sh — stamp template/ + okf_init into a new brain-* repo (HANDOFF §11 step 8).
#
# usage: init.sh <target-dir> [options]
#   <target-dir>     e.g. ../brain-eng; bundle id = basename minus "brain-" prefix
#   --site-host H    wiki hostname          (default: wiki.example.com)
#   --tier T         P1|P2|P3               (default: P1)
#   --ticket-regex R ticket id pattern      (default: ^[A-Z]+-[0-9]+$)
#   --bot-actor A    agent actor string     (default: wiki-kit/0.1)
#   --image I        lint container image   (default: ghcr.io/nineW0nW0n/wiki-kit:0.1.0)
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

target=""
site_host="wiki.example.com"
tier="P1"
ticket_regex='^[A-Z]+-[0-9]+$'
bot_actor="wiki-kit/0.1"
image="ghcr.io/nineW0nW0n/wiki-kit:0.1.0"

while [ $# -gt 0 ]; do
    case "$1" in
        --site-host)    site_host=$2;    shift 2 ;;
        --tier)         tier=$2;         shift 2 ;;
        --ticket-regex) ticket_regex=$2; shift 2 ;;
        --bot-actor)    bot_actor=$2;    shift 2 ;;
        --image)        image=$2;        shift 2 ;;
        -h|--help)      sed -n '2,11p' "$0"; exit 0 ;;
        -*)             echo "unknown option: $1" >&2; exit 2 ;;
        *)              target=$1;       shift ;;
    esac
done

[ -n "$target" ] || { echo "usage: init.sh <target-dir> [options]" >&2; exit 2; }
case "$tier" in P1|P2|P3) ;; *) echo "tier must be P1|P2|P3" >&2; exit 2 ;; esac

bundle_id=$(basename "$target")
bundle_id=${bundle_id#brain-}

if [ -e "$target" ] && [ -n "$(ls -A "$target" 2>/dev/null)" ]; then
    echo "refusing: $target exists and is not empty" >&2
    exit 1
fi

# 1. OKF scaffold (index.md, log.md, concepts/getting-started.md)
python3 "$here/okf_init.py" "$target" --title "$bundle_id"

# okf_init's generic concept lacks wiki-kit's required classification (lint rule 2)
gs="$target/getting-started.md"
awk -v t="$tier" 'NR==1 {print; print "classification: " t; next} {print}' \
    "$gs" > "$gs.tmp" && mv "$gs.tmp" "$gs"

# 2. Template on top (template's index.md/log.md win)
cp -R "$here/../template/." "$target/"

# 3. Placeholder substitution in text files
esc() { printf '%s' "$1" | sed 's/[&\\|]/\\&/g'; }
site_host_e=$(esc "$site_host"); tier_e=$(esc "$tier")
ticket_regex_e=$(esc "$ticket_regex"); bot_actor_e=$(esc "$bot_actor")
image_e=$(esc "$image"); bundle_id_e=$(esc "$bundle_id")

grep -rl '{{' "$target" | while IFS= read -r f; do
    sed -e "s|{{BUNDLE_ID}}|$bundle_id_e|g" \
        -e "s|{{SITE_HOST}}|$site_host_e|g" \
        -e "s|{{TIER}}|$tier_e|g" \
        -e "s|{{TICKET_REGEX}}|$ticket_regex_e|g" \
        -e "s|{{BOT_ACTOR}}|$bot_actor_e|g" \
        -e "s|{{IMAGE}}|$image_e|g" \
        "$f" > "$f.tmp" && mv "$f.tmp" "$f"
done

# 4. Git + hooks
if [ ! -d "$target/.git" ]; then
    git -C "$target" init -q -b main
fi
git -C "$target" add -A
if command -v pre-commit >/dev/null 2>&1; then
    (cd "$target" && pre-commit install >/dev/null)
    hooks="installed"
else
    hooks="NOT installed (pre-commit missing; run 'pre-commit install' later)"
fi

echo "bundle '$bundle_id' created at $target"
echo "  site: https://$site_host/$bundle_id/  tier: $tier"
echo "  pre-commit hooks: $hooks"
echo "next: review, then 'git -C $target commit -m \"chore: scaffold bundle\"'"
