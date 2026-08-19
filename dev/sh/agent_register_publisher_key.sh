#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env

TARGET="$(upper "${1:-COM}")"
case "$TARGET" in
    COM|CN) ;;
    *) echo "Usage: $0 COM|CN" >&2; exit 2 ;;
esac

case "${THEUMST_PUBLISHER_KEY_HASH:-}" in
    (*[!0-9a-f]*|'') echo "A lowercase SHA-256 THEUMST_PUBLISHER_KEY_HASH is required" >&2; exit 1 ;;
esac
[ "${#THEUMST_PUBLISHER_KEY_HASH}" -eq 64 ] || {
    echo "THEUMST_PUBLISHER_KEY_HASH must contain 64 hex characters" >&2
    exit 1
}
PUBLISHER_PREFIX="${THEUMST_PUBLISHER_KEY_PREFIX:-}"
[ "${#PUBLISHER_PREFIX}" -ge 8 ] || {
    echo "THEUMST_PUBLISHER_KEY_PREFIX must contain at least 8 characters" >&2
    exit 1
}

remote_context "$TARGET"
SOURCE_KEY="$KEY"
RUNTIME_SSH_KEY_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t theumst_ssh)"
cleanup_runtime_key() {
    rm -rf -- "$RUNTIME_SSH_KEY_DIR"
}
trap cleanup_runtime_key EXIT
cp "$SOURCE_KEY" "$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
chmod 600 "$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
KEY="$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
SUDO="$(remote_sudo)"

ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" \
    "cd '$REMOTE_ROOT' && $SUDO docker compose --env-file .env -f compose.deploy.yml exec -T \
        -e THEUMST_PUBLISHER_KEY_HASH='$THEUMST_PUBLISHER_KEY_HASH' \
        -e THEUMST_PUBLISHER_KEY_PREFIX='$THEUMST_PUBLISHER_KEY_PREFIX' \
        backend python -m scripts.register_publisher_key"
