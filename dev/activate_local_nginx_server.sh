#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"
trap 'say "Local activation failed."' ERR

say "Activating local server."

BACKEND_PYTHON="$(umst_backend_python)" || fail "Missing backend venv. Run dev/initialize_local.sh first."
"$SCRIPT_DIR/build_dashboard_local.sh"

mkdir -p "$LOCAL_LOG_DIR"
if umst_port_listening "$BACKEND_PORT"; then
    echo "Backend already running on port $BACKEND_PORT."
else
    echo "Starting backend on http://127.0.0.1:$BACKEND_PORT ..."
    (
        cd "$ROOT/backend/python"
        export DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT LOCAL_STORAGE_DIR SERVER
        "$BACKEND_PYTHON" -m uvicorn app:app --host 127.0.0.1 --port "$BACKEND_PORT"
    ) > "$LOCAL_LOG_DIR/backend.log" 2>&1 &
    echo $! > "$LOCAL_STATE_DIR/backend.pid"
    sleep 1
fi

if ! command -v "$NGINX_BIN" >/dev/null 2>&1 && [ ! -x "$NGINX_BIN" ]; then
    fail "Missing nginx at '$NGINX_BIN'. On Ubuntu: sudo apt install nginx"
fi

umst_write_local_nginx_conf
umst_nginx -t

if [ -f "$LOCAL_NGINX_PREFIX/nginx.pid" ] && kill -0 "$(cat "$LOCAL_NGINX_PREFIX/nginx.pid")" >/dev/null 2>&1; then
    umst_nginx -s reload
else
    umst_nginx
fi

say "Local server is active."
echo "Open: $LOCAL_URL"
echo "Logs: $LOCAL_LOG_DIR/backend.log and $LOCAL_LOG_DIR/nginx.error.log"
umst_pause_if_requested
