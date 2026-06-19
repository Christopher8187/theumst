#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/load_env.sh"
trap 'say "Giving server permissions failed."' ERR

say "Giving server permissions."
ssh -i "$KEY" "$REMOTE" "$SUDO mkdir -p $REMOTE_ROOT && $SUDO chown -R $SSH_USER:$NGINX_USER $REMOTE_ROOT && $SUDO find $REMOTE_ROOT -path '*/.venv/*' -prune -o -path '*/node_modules/*' -prune -o -type d -exec chmod 2755 {} \; && $SUDO find $REMOTE_ROOT -path '*/.venv/*' -prune -o -path '*/node_modules/*' -prune -o -type f -exec chmod 644 {} \; && $SUDO chmod 755 /var /var/www"
say "Server permissions fixed."
umst_pause_if_requested
