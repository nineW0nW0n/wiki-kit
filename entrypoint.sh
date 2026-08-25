#!/bin/sh
# wiki-kit entrypoint. Subcommands:
#   lint <bundle> [args...]      run scripts/lint.py
#   validate <bundle> [args...]  run vendored okf_validate.py
#   <anything else>              exec verbatim (shell, python3, ...)
# The builder loop (HANDOFF §7) lands here at step 6.
set -eu

cmd="${1:-}"
[ $# -gt 0 ] && shift

case "$cmd" in
    lint)
        exec python3 /app/scripts/lint.py "$@"
        ;;
    validate)
        exec python3 /app/scripts/okf_validate.py "$@"
        ;;
    "")
        echo "usage: lint|validate <bundle> [args...], or any command to exec" >&2
        exit 2
        ;;
    *)
        exec "$cmd" "$@"
        ;;
esac
