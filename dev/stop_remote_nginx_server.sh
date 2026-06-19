#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/load_env.sh"
trap 'say "Stopping remote server failed."' ERR

say "Stopping remote server."
ssh -i "$KEY" "$REMOTE" "$SUDO systemctl stop nginx || true; $SUDO systemctl stop $BACKEND_SERVICE || true"
say "Remote server stopped."
umst_pause_if_requested
