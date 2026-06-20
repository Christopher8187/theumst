#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"

SSH_KEY_VAR="SSH_KEY_$TARGET_SERVER"
SSH_USER_VAR="SSH_USER_$TARGET_SERVER"
SSH_HOST_VAR="SSH_HOST_$TARGET_SERVER"
KEY_NAME="$(remote_value "$SSH_KEY_VAR")"
SSH_USER="$(remote_value "$SSH_USER_VAR")"
SSH_HOST="$(remote_value "$SSH_HOST_VAR")"
SSH_KEY_DIR="${SSH_KEY_DIR:-$HOME/.ssh}"
KEY="$SSH_KEY_DIR/$KEY_NAME"
REMOTE="$SSH_USER@$SSH_HOST"
[ -f "$KEY" ] || { echo "Missing SSH key: $KEY" >&2; exit 1; }
exec ssh -i "$KEY" "$REMOTE"
