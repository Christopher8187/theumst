#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"

SSH_KEY_VAR="SSH_KEY_$TARGET_SERVER"
SSH_USER_VAR="SSH_USER_$TARGET_SERVER"
SSH_HOST_VAR="SSH_HOST_$TARGET_SERVER"
SUDO_PASSWORD_VAR="SUDO_PASSWORD_$TARGET_SERVER"
KEY_NAME="$(remote_value "$SSH_KEY_VAR")"
SSH_USER="$(remote_value "$SSH_USER_VAR")"
SSH_HOST="$(remote_value "$SSH_HOST_VAR")"
SUDO_PASSWORD="$(remote_value "$SUDO_PASSWORD_VAR")"
SSH_KEY_DIR="${SSH_KEY_DIR:-$HOME/.ssh}"
KEY="$SSH_KEY_DIR/$KEY_NAME"
REMOTE="$SSH_USER@$SSH_HOST"
SUDO="printf '%s\n' '$SUDO_PASSWORD' | sudo -S -p ''"

[ -n "$KEY_NAME$SSH_USER$SSH_HOST" ] || { echo "Missing SSH settings for $TARGET_SERVER in .env" >&2; exit 1; }
[ -f "$KEY" ] || { echo "Missing SSH key: $KEY" >&2; exit 1; }

echo "Installing Docker on $REMOTE..."
ssh -i "$KEY" "$REMOTE" "$SUDO apt update && $SUDO apt install -y ca-certificates curl gnupg && curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && $SUDO sh /tmp/get-docker.sh && $SUDO usermod -aG docker $SSH_USER"

echo "Remote Docker setup is ready. Log out/in on the server if docker permissions do not refresh immediately."
