#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/load_env.sh"
trap 'say "Upload failed."' ERR

STAGE="$(mktemp -d 2>/dev/null || mktemp -d -t theumst_upload)"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

say "Preparing upload folder."
(
    cd "$ROOT"
    tar \
        --exclude='./.env' \
        --exclude='./.git' \
        --exclude='./.venv' \
        --exclude='./__pycache__' \
        --exclude='./.local' \
        --exclude='./frontend/webpage/node_modules' \
        --exclude='./frontend/webpage/dist' \
        --exclude='./frontend/dashboard/node_modules' \
        --exclude='./frontend/dashboard/dist' \
        -cf - . | (cd "$STAGE" && tar -xf -)
)

say "Uploading all files to server."
ssh -i "$KEY" "$REMOTE" "mkdir -p $REMOTE_ROOT"
scp -i "$KEY" -r "$STAGE"/. "$REMOTE:$REMOTE_ROOT/"

say "Fixing server permissions."
ssh -i "$KEY" "$REMOTE" "$SUDO chown -R $SSH_USER:$NGINX_USER $REMOTE_ROOT && $SUDO find $REMOTE_ROOT -path '*/.venv/*' -prune -o -path '*/node_modules/*' -prune -o -type d -exec chmod 2755 {} \; && $SUDO find $REMOTE_ROOT -path '*/.venv/*' -prune -o -path '*/node_modules/*' -prune -o -type f -exec chmod 644 {} \; && $SUDO chmod 755 /var /var/www"

say "Upload complete."
umst_pause_if_requested
