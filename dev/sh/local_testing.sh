#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env

cat <<'MENU'
Local testing:
  1) Start
  2) Check
  3) Logs
  4) Stop
  5) Build
  6) Reset volumes/database
  7) Quit
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) local_start ;;
    2) local_check ;;
    3) local_logs ;;
    4) local_stop ;;
    5) local_build ;;
    6) local_reset ;;
    7|q|Q|quit|exit) ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
