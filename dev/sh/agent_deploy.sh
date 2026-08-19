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

# OpenSSH correctly refuses private keys exposed by permissive Windows-mount
# modes (for example 0777 under WSL/DrvFS). Stage only the selected key in a
# private Linux temporary directory for this process, then remove it on every
# exit path. The source key and its Windows ACLs are left untouched.
SOURCE_SSH_KEY_DIR="$SSH_KEY_DIR"
KEY_NAME="$(remote_setting "SSH_KEY_${TARGET}")"
[ -n "$KEY_NAME" ] || { echo "Missing SSH_KEY_${TARGET} in .env" >&2; exit 1; }
RUNTIME_SSH_KEY_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t theumst_ssh)"
cleanup_runtime_key() {
    rm -rf -- "$RUNTIME_SSH_KEY_DIR"
}
trap cleanup_runtime_key EXIT
cp "$SOURCE_SSH_KEY_DIR/$KEY_NAME" "$RUNTIME_SSH_KEY_DIR/$KEY_NAME"
chmod 600 "$RUNTIME_SSH_KEY_DIR/$KEY_NAME"
export THEUMST_SSH_KEY_DIR="$RUNTIME_SSH_KEY_DIR"

for command in ssh scp tar gzip curl; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Required command is missing: $command" >&2
        exit 1
    }
done

remote_full_deploy "$TARGET"
