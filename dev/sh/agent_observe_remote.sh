#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_env

TARGET="$(upper "${1:-COM}")"
case "$TARGET" in
    COM|CN) ;;
    *) echo "Usage: $0 COM|CN" >&2; exit 2 ;;
esac

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
    "cd '$REMOTE_ROOT' && \
     $SUDO docker compose --env-file .env -f compose.deploy.yml ps && \
     $SUDO docker stats --no-stream --format 'table {{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}' \
       theumst-deploy-backend-1 theumst-deploy-db-1 theumst-deploy-qdrant-1 && \
     $SUDO docker compose --env-file .env -f compose.deploy.yml logs --tail=80 backend"
