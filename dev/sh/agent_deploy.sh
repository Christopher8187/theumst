#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env

TARGET="$(upper "${1:-${REMOTE_SERVER:-COM}}")"
case "$TARGET" in
    COM|CN) ;;
    *) echo "Usage: $0 COM|CN" >&2; exit 2 ;;
esac

for command in ssh scp tar gzip curl; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Required command is missing: $command" >&2
        exit 1
    }
done

remote_full_deploy "$TARGET"
