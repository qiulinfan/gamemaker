#!/bin/sh
set -eu

skip_link_check=0
codex_home=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --skip-link-check) skip_link_check=1 ;;
        --codex-home)
            shift
            [ "$#" -gt 0 ] || { echo "--codex-home requires a path" >&2; exit 2; }
            codex_home=$1
            ;;
        *)
            [ -z "$codex_home" ] || { echo "Unexpected argument: $1" >&2; exit 2; }
            codex_home=$1
            ;;
    esac
    shift
done

[ -n "$codex_home" ] || codex_home=${CODEX_HOME:-"$HOME/.codex"}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
if command -v python3 >/dev/null 2>&1; then python_bin=python3
elif command -v python >/dev/null 2>&1; then python_bin=python
else echo "Python 3.11+ is required for bundle validation." >&2; exit 1
fi
command -v uv >/dev/null 2>&1 || {
    echo "uv is required for locked Skill runtimes and validation." >&2
    exit 1
}

set -- "$python_bin" "$script_dir/posix_link_manager.py" doctor --root "$repo_root" --codex-home "$codex_home"
[ "$skip_link_check" -eq 0 ] || set -- "$@" --skip-link-check
exec "$@"
