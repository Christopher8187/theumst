#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"
trap 'say "Stopping local server failed."' ERR

say "Stopping local server."

umst_stop_process_on_port "$BACKEND_PORT" || true

if [ -f "$LOCAL_NGINX_PREFIX/nginx.pid" ]; then
    if command -v "$NGINX_BIN" >/dev/null 2>&1 || [ -x "$NGINX_BIN" ]; then
        umst_nginx -s quit >/dev/null 2>&1 || true
    fi
    rm -f "$LOCAL_NGINX_PREFIX/nginx.pid"
elif umst_is_windows && command -v taskkill >/dev/null 2>&1; then
    taskkill //IM nginx.exe //F >/dev/null 2>&1 || true
fi

say "Local server stopped."
umst_pause_if_requested
