#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"
trap 'say "Testing pipeline failed to start."' ERR

say "Starting FastAPI and Vite testing pipeline."
mkdir -p "$LOCAL_LOG_DIR"

BACKEND_PYTHON="$(umst_backend_python)" || fail "Missing backend venv. Run dev/initialize_local.sh first."
umst_find_npm || fail "Missing npm. Install Node.js LTS, then reopen your terminal."

if umst_port_listening "$BACKEND_PORT"; then
    echo "FastAPI already running on http://127.0.0.1:$BACKEND_PORT"
else
    echo "Starting FastAPI on http://127.0.0.1:$BACKEND_PORT ..."
    (
        cd "$ROOT/backend/python"
        export DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT LOCAL_STORAGE_DIR SERVER CORS_ORIGINS
        "$BACKEND_PYTHON" -m uvicorn app:app --host 127.0.0.1 --port "$BACKEND_PORT"
    ) > "$LOCAL_LOG_DIR/backend.log" 2>&1 &
    echo $! > "$LOCAL_STATE_DIR/backend.pid"
fi

start_vite() {
    local name="$1"
    local dir="$2"
    local port="$3"
    local pid_file="$4"
    local log_file="$5"

    if umst_port_listening "$port"; then
        echo "$name already running on http://127.0.0.1:$port"
        return 0
    fi

    if [ ! -d "$dir/node_modules" ]; then
        echo "Installing $name packages..."
        (cd "$dir" && "${UMST_NPM[@]}" install --no-audit --no-fund)
    fi

    echo "Starting $name on http://127.0.0.1:$port ..."
    (
        cd "$dir"
        "${UMST_NPM[@]}" run dev
    ) > "$log_file" 2>&1 &
    echo $! > "$pid_file"
}

start_vite "Vue webpage" "$WEBPAGE_DIR" "$WEBPAGE_PORT" "$LOCAL_STATE_DIR/webpage.pid" "$LOCAL_LOG_DIR/webpage.log"
start_vite "Vue dashboard" "$DASHBOARD_DIR" "$DASHBOARD_PORT" "$LOCAL_STATE_DIR/dashboard.pid" "$LOCAL_LOG_DIR/dashboard.log"

say "Testing pipeline is active."
echo "Backend:   http://localhost:$BACKEND_PORT"
echo "Webpage:   http://localhost:$WEBPAGE_PORT"
echo "Dashboard: http://localhost:$DASHBOARD_PORT/dashboard/profile/"
echo "Main URL:  http://localhost:$WEBPAGE_PORT"
echo "Logs:      $LOCAL_LOG_DIR"
umst_pause_if_requested
