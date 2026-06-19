#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/load_env.sh"
BAD=0

echo "=== Remote server diagnosis ==="
echo "Remote: $REMOTE"
echo "URL:    $REMOTE_URL"
echo

ssh -i "$KEY" "$REMOTE" "echo SSH OK" || fail "Remote check failed before starting."

if ssh -i "$KEY" "$REMOTE" "$SUDO systemctl is-active --quiet postgresql"; then
    echo "OK: PostgreSQL is active."
else
    echo "DIAGNOSIS: PostgreSQL is not active."
    BAD=1
fi

if ssh -i "$KEY" "$REMOTE" "$SUDO systemctl is-active --quiet $BACKEND_SERVICE"; then
    echo "OK: Backend is active."
else
    echo "DIAGNOSIS: Backend service is not active. Run dev/activate_remote_nginx_server.sh."
    BAD=1
fi

if ssh -i "$KEY" "$REMOTE" "curl -s --max-time 5 http://127.0.0.1:$BACKEND_PORT/health"; then
    echo "OK: Backend health check passed."
else
    echo "DIAGNOSIS: Backend health check failed."
    BAD=1
fi

if ssh -i "$KEY" "$REMOTE" "test -f $REMOTE_DASHBOARD/dist/index.html"; then
    echo "OK: Vue dashboard build exists."
else
    echo "DIAGNOSIS: Vue dashboard is not built. Run dev/activate_remote_nginx_server.sh."
    BAD=1
fi

if ssh -i "$KEY" "$REMOTE" "$SUDO nginx -t"; then
    echo "OK: Nginx config is valid."
else
    echo "DIAGNOSIS: Nginx config is invalid."
    BAD=1
fi

if ssh -i "$KEY" "$REMOTE" "$SUDO systemctl is-active --quiet nginx"; then
    echo "OK: Nginx is active."
else
    echo "DIAGNOSIS: Nginx is not active."
    BAD=1
fi

curl -IL --max-redirs 10 --max-time 20 "$REMOTE_URL" || BAD=1
curl -IL --max-redirs 10 --max-time 20 "$REMOTE_URL/login" || BAD=1
curl -IL --max-redirs 10 --max-time 20 "$REMOTE_URL/dashboard/profile/" || BAD=1

echo
if [ "$BAD" = "0" ]; then
    echo "FINAL DIAGNOSIS: Remote server looks healthy."
    say "Remote server looks healthy."
else
    echo "FINAL DIAGNOSIS: Remote server has problems."
    say "Remote server has problems."
fi
umst_pause_if_requested
exit 0
