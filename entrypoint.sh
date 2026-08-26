#!/bin/sh
# wiki-kit entrypoint. Subcommands:
#   lint <bundle> [args...]      run scripts/lint.py
#   validate <bundle> [args...]  run vendored okf_validate.py
#   loop | <none>                builder loop (HANDOFF §7)
#   <anything else>              exec verbatim (shell, python3, ...)
set -eu

APP="${APP:-/app}"
BUNDLES_FILE="${BUNDLES_FILE:-/etc/wiki/bundles.yml}"
BUNDLES_DIR="${BUNDLES_DIR:-/bundles}"
SITE_DIR="${SITE_DIR:-/site}"
STATE_DIR="${STATE_DIR:-/state}"

cfg() {  # cfg <yaml-path-expr>  e.g. cfg "site_host"
    python3 -c "import sys,yaml; print(yaml.safe_load(open('$BUNDLES_FILE')).get('$1',''))"
}

bundles_tsv() {  # id \t repo \t branch \t ticket_regex
    python3 - "$BUNDLES_FILE" <<'EOF'
import sys, yaml
for b in yaml.safe_load(open(sys.argv[1]))["bundles"]:
    print("\t".join([b["id"], b["repo"], b.get("branch", "main"),
                     b.get("ticket_regex", "")]))
EOF
}

auth_url() {  # inject read-only token into https github URLs when present
    url="$1"
    token="${GIT_TOKEN:-}"
    [ -z "$token" ] && [ -r /run/secrets/git_token ] && token="$(cat /run/secrets/git_token)"
    case "$url" in
        https://*) [ -n "$token" ] && echo "https://x-access-token:${token}@${url#https://}" \
                       || echo "$url" ;;
        *) echo "$url" ;;
    esac
}

sync_bundle() {  # sync_bundle <id> <repo> <branch> — idempotent checkout
    dir="$BUNDLES_DIR/$1"
    if [ -d "$dir/.git" ]; then
        git -C "$dir" fetch --depth 1 origin "$3"
        git -C "$dir" reset --hard FETCH_HEAD
        git -C "$dir" clean -fdx   # wipes last cycle's generated pages too
    else
        rm -rf "$dir"
        git clone --depth 1 -b "$3" "$(auth_url "$2")" "$dir"
    fi
}

run_loop() {
    [ -f "$BUNDLES_FILE" ] || { echo "no bundles file at $BUNDLES_FILE" >&2; exit 1; }
    mkdir -p "$BUNDLES_DIR" "$SITE_DIR" "$STATE_DIR"
    exec 9>"$STATE_DIR/lock"
    flock -n 9 || { echo "another builder holds $STATE_DIR/lock" >&2; exit 1; }

    # single-purpose container: uid mismatches on mounted repos are fine
    git config --global --add safe.directory '*'

    SITE_HOST="$(cfg site_host)"
    export SITE_HOST BUNDLES_DIR SITE_DIR
    INTERVAL="${INTERVAL:-$(cfg interval_seconds)}"
    INTERVAL="${INTERVAL:-900}"

    while :; do
        results="$STATE_DIR/results.tsv"
        : > "$results"
        bundles_tsv | while IFS="$(printf '\t')" read -r id repo branch ticket_regex; do
            sync_bundle "$id" "$repo" "$branch" \
                || { echo "$id	sync-failed	1	no" >> "$results"; continue; }
            sha="$(git -C "$BUNDLES_DIR/$id" rev-parse HEAD)"
            set -- "$BUNDLES_DIR/$id"
            [ -n "$ticket_regex" ] && set -- "$@" --ticket-regex "$ticket_regex"
            if python3 "$APP/scripts/lint.py" "$@"; then lint_rc=0; else lint_rc=$?; fi
            echo "$id	$sha	$lint_rc	pending" >> "$results"
        done

        python3 "$APP/scripts/build_index.py" --bundles "$BUNDLES_FILE" \
            --root "$BUNDLES_DIR" --db "$STATE_DIR/wiki.db" || true

        while IFS="$(printf '\t')" read -r id sha lint_rc _; do
            if [ "$lint_rc" = 0 ]; then
                if "$APP/scripts/build_site.sh" "$id"; then
                    python3 "$APP/scripts/okf_visualize.py" "$BUNDLES_DIR/$id" \
                        -o "$SITE_DIR/$id/viz.html" -t "$id" || true
                    built=yes
                else
                    built=failed   # last good site stays in place
                fi
            else
                built=skipped
            fi
            echo "$id	$sha	$lint_rc	$built" >> "$results.done"
        done < "$results"
        mv "$results.done" "$results"

        python3 - "$results" "$STATE_DIR/status.json" "$SITE_DIR/index.html" <<'EOF'
import html, json, sys, time
rows = [l.rstrip("\n").split("\t") for l in open(sys.argv[1]) if l.strip()]
updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
status = {"updated": updated,
          "bundles": {r[0]: {"sha": r[1], "lint_exit": int(r[2]), "build": r[3]}
                      for r in rows}}
json.dump(status, open(sys.argv[2], "w"), indent=1)

# root index: bare host lands here instead of a 404 (served by Caddy try_files)
items = "\n".join(
    '<li><a href="/{0}/">{0}</a> <small>({1})</small></li>'.format(
        html.escape(r[0]), html.escape(r[3])) for r in rows)
open(sys.argv[3], "w").write("""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>wiki</title>
<style>body{{font:16px/1.5 system-ui;max-width:40rem;margin:2rem auto;padding:0 1rem}}
small{{color:#888}}</style>
<h1>wiki</h1>
<ul>
{items}
</ul>
<p><small>updated {updated}</small></p>
""".format(items=items, updated=updated))
EOF
        echo "cycle done; sleeping ${INTERVAL}s"
        sleep "$INTERVAL"
    done
}

cmd="${1:-loop}"
[ $# -gt 0 ] && shift

case "$cmd" in
    lint)     exec python3 "$APP/scripts/lint.py" "$@" ;;
    validate) exec python3 "$APP/scripts/okf_validate.py" "$@" ;;
    loop)     run_loop ;;
    *)        exec "$cmd" "$@" ;;
esac
