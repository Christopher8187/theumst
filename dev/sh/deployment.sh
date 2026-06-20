#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env

cat <<'MENU'
Deployment:
  1) Start local nginx-style stack
  2) Check local nginx-style stack
  3) Logs
  4) Stop
  5) Reset volumes/database
  6) Remote full deploy
  7) Remote setup Docker/certbot
  8) Remote upload only
  9) Remote start only
 10) Remote stop only
 11) Remote shell
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) deploy_start ;;
    2) deploy_check ;;
    3) deploy_logs ;;
    4) deploy_stop ;;
    5) deploy_reset ;;
    6) server="$(pick_server)"; remote_full_deploy "$server" ;;
    7) server="$(pick_server)"; remote_setup "$server" ;;
    8) server="$(pick_server)"; remote_upload "$server" ;;
    9) server="$(pick_server)"; remote_start "$server" ;;
   10) server="$(pick_server)"; remote_stop "$server" ;;
   11) server="$(pick_server)"; remote_shell "$server" ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
