#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env

cat <<'MENU'
Permission actions:
  1) Give local dev/sh scripts execute permission
  2) Fix local project ownership/writable files
  3) Fix local Docker permission for this Linux user
  4) Test local Docker permission
  5) Fix remote COM permissions
  6) Fix remote CN permissions
  7) Choose remote server to fix permissions
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) fix_local_script_permissions ;;
    2) fix_local_project_permissions ;;
    3) fix_local_docker_group ;;
    4) test_local_docker_permissions ;;
    5) remote_permissions COM ;;
    6) remote_permissions CN ;;
    7) server="$(pick_server)"; remote_permissions "$server" ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
