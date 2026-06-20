#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
load_env
need_docker

show_menu() {
    cat <<'MENU'
Local testing uses hot reload:
  Webpage   http://localhost:5173       or http://127.0.0.1:5173
  Dashboard http://localhost:5174/dashboard/profile/
  FastAPI   http://localhost:8000       or http://127.0.0.1:8000

Choose an action:
  1) Start local testing and check ports
  2) Check local testing
  3) Show local logs
  4) Stop local testing
  5) Build local images
  6) Reset local volumes/database
  7) Quit
MENU
}

start_local_testing() {
    echo "Starting local Docker stack..."
    local_compose up --build -d --remove-orphans
    echo
    echo "Container status after start:"
    local_compose ps
    echo
    echo "Checking local ports/health..."
    wait_for_local_testing || {
        echo
        echo "At least one service is not reachable or has crashed. Recent logs:" >&2
        local_compose logs --tail=160 db backend webpage dashboard >&2 || true
        return 1
    }
    open_local_urls
}

url_ok() {
    url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS --max-time 3 "$url" >/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -q --spider --timeout=3 "$url" >/dev/null 2>&1
    else
        echo "Neither curl nor wget is installed on the host, so I cannot check URLs." >&2
        return 1
    fi
}

wait_for_url() {
    name="$1"
    url="$2"
    printf '  Waiting for %s  %s' "$name" "$url"
    for _ in $(seq 1 45); do
        if url_ok "$url"; then
            printf '  OK\n'
            return 0
        fi
        printf '.'
        sleep 1
    done
    printf '  FAIL\n' >&2
    return 1
}

wait_for_local_testing() {
    local status=0
    wait_for_url "FastAPI" "http://127.0.0.1:8000/health" || status=1
    wait_for_url "Database" "http://127.0.0.1:8000/health/db" || status=1
    wait_for_url "Assets" "http://127.0.0.1:8000/health/assets" || status=1
    wait_for_url "Webpage" "http://127.0.0.1:5173/" || status=1
    wait_for_url "Dashboard" "http://127.0.0.1:5174/dashboard/profile/" || status=1
    return "$status"
}

check_one_url() {
    name="$1"
    url="$2"
    if url_ok "$url"; then
        printf '  OK   %s  %s\n' "$name" "$url"
        return 0
    fi
    printf '  FAIL %s  %s\n' "$name" "$url" >&2
    return 1
}

check_local_testing() {
    local status=0
    local_compose ps || status=1
    echo
    check_one_url "FastAPI" "http://127.0.0.1:8000/health" || status=1
    check_one_url "Database" "http://127.0.0.1:8000/health/db" || status=1
    check_one_url "Assets" "http://127.0.0.1:8000/health/assets" || status=1
    check_one_url "Webpage" "http://127.0.0.1:5173/" || status=1
    check_one_url "Dashboard" "http://127.0.0.1:5174/dashboard/profile/" || status=1
    return "$status"
}

while true; do
    show_menu
    choice="$(choose "Action" "1")"
    echo

    case "$choice" in
        1) start_local_testing ;;
        2) check_local_testing ;;
        3) local_compose logs -f ;;
        4) local_compose down ;;
        5) local_compose build --no-cache ;;
        6) local_compose down -v ;;
        7|q|Q|quit|exit) break ;;
        *) echo "No valid action selected." ;;
    esac

    echo
    if [ -t 0 ]; then
        printf 'Press Enter to return to the menu...'
        IFS= read -r _ || true
        echo
    else
        break
    fi
done
