#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env

cat <<'MENU'
Health checks:
  1) Local testing
  2) Local nginx-style deployment
  3) Remote COM
  4) Remote CN
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) local_check ;;
    2) deploy_check ;;
    3) remote_check COM ;;
    4) remote_check CN ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
