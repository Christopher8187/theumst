#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_env

cat <<'MENU'
Health checks:
  1) Local testing stack
  2) Deployment-style local nginx stack
  3) Remote COM server
  4) Remote CN server
  5) All local checks
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) need_docker; local_compose ps; echo; health_url http://localhost:8000/health ;;
    2) need_docker; deploy_compose ps; echo; health_url "http://localhost:${HTTP_PORT:-8080}/health" ;;
    3) remote_check COM ;;
    4) remote_check CN ;;
    5) need_docker; echo "Local testing:"; local_compose ps; echo; echo "Deployment-style local:"; deploy_compose ps; echo; health_url http://localhost:8000/health; health_url "http://localhost:${HTTP_PORT:-8080}/health" ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
