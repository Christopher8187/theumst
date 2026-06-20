#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_env

cat <<'MENU'
Permission actions:
  1) Give local dev/sh scripts execute permission
  2) Fix remote COM permissions
  3) Fix remote CN permissions
  4) Choose remote server to fix permissions
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) chmod +x "$SCRIPT_DIR"/*.sh; echo "Made dev/sh/*.sh executable." ;;
    2) remote_permissions COM ;;
    3) remote_permissions CN ;;
    4) server="$(pick_server)"; remote_permissions "$server" ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
