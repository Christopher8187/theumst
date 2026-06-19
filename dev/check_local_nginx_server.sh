#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"
BAD=0

echo "=== Local server diagnosis ==="
echo "ROOT=$ROOT"
echo "LOCAL_URL=$LOCAL_URL"
echo "Backend=http://127.0.0.1:$BACKEND_PORT"
echo

if umst_port_listening "$BACKEND_PORT"; then
    echo "OK: Backend is running."
else
    echo "DIAGNOSIS: Backend is not running. Run dev/activate_local_nginx_server.sh."
    BAD=1
fi

if curl -s --max-time 5 "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null; then
    echo "OK: Backend health check passed."
else
    echo "DIAGNOSIS: Backend health check failed."
    BAD=1
fi

if [ -f "$DASHBOARD_DIR/dist/index.html" ]; then
    echo "OK: Vue dashboard build exists."
else
    echo "DIAGNOSIS: Vue dashboard is not built. Run dev/initialize_local.sh or dev/activate_local_nginx_server.sh."
    BAD=1
fi

if command -v "$NGINX_BIN" >/dev/null 2>&1 || [ -x "$NGINX_BIN" ]; then
    echo "OK: Nginx binary found: $NGINX_BIN"
    umst_write_local_nginx_conf
    if umst_nginx -t; then
        echo "OK: Local Nginx config is valid."
    else
        echo "DIAGNOSIS: Local Nginx config is invalid."
        BAD=1
    fi
else
    echo "DIAGNOSIS: Nginx was not found at '$NGINX_BIN'."
    BAD=1
fi

if [ -f "$LOCAL_NGINX_PREFIX/nginx.pid" ] && kill -0 "$(cat "$LOCAL_NGINX_PREFIX/nginx.pid")" >/dev/null 2>&1; then
    echo "OK: Local Nginx process is running."
else
    echo "DIAGNOSIS: Local Nginx is not running."
    BAD=1
fi

curl -IL --max-time 5 "$LOCAL_URL" || BAD=1
curl -IL --max-time 5 "$LOCAL_URL/login" || BAD=1
curl -IL --max-time 5 "$LOCAL_URL/dashboard/profile/" || BAD=1

echo
if [ "$BAD" = "0" ]; then
    echo "FINAL DIAGNOSIS: Local server looks healthy."
    say "Local server looks healthy."
else
    echo "FINAL DIAGNOSIS: Local server has problems."
    say "Local server has problems."
fi
umst_pause_if_requested
exit 0
