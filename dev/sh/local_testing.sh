#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env
need_docker

cat <<'MENU'
Local testing uses hot reload:
  Webpage   http://localhost:5173
  Dashboard http://localhost:5174/dashboard/profile/
  FastAPI   http://localhost:8000

Choose an action:
  1) Start local testing
  2) Check local testing
  3) Show local logs
  4) Stop local testing
  5) Build local images
  6) Reset local volumes/database
MENU
choice="$(choose "Action" "1")"

case "$choice" in
    1) local_compose up --build -d; open_local_urls ;;
    2) local_compose ps; echo; echo "FastAPI health:"; health_url http://localhost:8000/health ;;
    3) local_compose logs -f ;;
    4) local_compose down ;;
    5) local_compose build ;;
    6) local_compose down -v ;;
    *) echo "No action selected." ;;
esac
pause_if_clicked
