#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_env

cat <<'MENU'
Certificate actions:
  1) Renew/issue COM certificate
  2) Renew/issue CN certificate
  3) Choose target server
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) remote_certs COM ;;
    2) remote_certs CN ;;
    3) server="$(pick_server)"; remote_certs "$server" ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
