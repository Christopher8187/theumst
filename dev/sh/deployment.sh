#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env

cat <<'MENU'
Deployment actions:
  1) Start deployment-style local nginx stack
  2) Check deployment-style local nginx stack
  3) Show deployment-style local logs
  4) Stop deployment-style local nginx stack
  5) Reset deployment-style local volumes/database
  6) Remote full deploy: permissions + upload + start + check
  7) Remote setup Docker/certbot
  8) Remote upload only
  9) Remote start only
 10) Remote stop only
 11) Remote shell
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) need_docker; deploy_compose up --build -d; open_deploy_url ;;
    2) need_docker; deploy_compose ps; echo; echo "Nginx health:"; health_url "http://localhost:${HTTP_PORT:-8080}/health" ;;
    3) need_docker; deploy_compose logs -f ;;
    4) need_docker; deploy_compose down ;;
    5) need_docker; deploy_compose down -v ;;
    6) server="$(pick_server)"; remote_full_deploy "$server" ;;
    7) server="$(pick_server)"; remote_setup "$server" ;;
    8) server="$(pick_server)"; remote_upload "$server" ;;
    9) server="$(pick_server)"; remote_start "$server" ;;
   10) server="$(pick_server)"; remote_stop "$server" ;;
   11) server="$(pick_server)"; remote_shell "$server" ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
