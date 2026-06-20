#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env

echo "Project root: $ROOT"
echo

echo "1) Making shell scripts executable..."
chmod +x "$SCRIPT_DIR"/*.sh

echo "2) Making project files owned/writable by this Linux user..."
sudo chown -R "$USER:$USER" "$ROOT"
find "$ROOT/dev/sh" -type f -name '*.sh' -exec chmod u+x {} \;
find "$ROOT" -type d -exec chmod u+rwx {} \;
find "$ROOT" -type f -exec chmod u+rw {} \;

echo "3) Starting Docker service if systemd is available..."
sudo systemctl enable --now docker 2>/dev/null || true

if command -v docker >/dev/null 2>&1; then
    echo "4) Adding $USER to the docker group..."
    if groups "$USER" | tr ' ' '\n' | grep -qx docker; then
        echo "$USER is already in the docker group."
    else
        sudo usermod -aG docker "$USER"
        echo "Added $USER to docker group."
    fi
else
    echo "Docker command not found. Install Docker first, then run this again."
fi

cat <<'HELP'

Linux permissions are repaired.

Now refresh Docker group membership using ONE of these:
  newgrp docker

or fully log out and log back in.

Then test Docker:
  docker run --rm hello-world

Then start the app:
  ./dev/sh/local_testing.sh
HELP

pause_if_clicked
