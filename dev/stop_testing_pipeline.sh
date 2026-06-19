#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"
trap 'say "Stopping testing pipeline failed."' ERR

say "Stopping FastAPI and Vite testing pipeline."
umst_stop_process_on_port "$WEBPAGE_PORT" "$LOCAL_STATE_DIR/webpage.pid" || true
umst_stop_process_on_port "$DASHBOARD_PORT" "$LOCAL_STATE_DIR/dashboard.pid" || true
umst_stop_process_on_port "$BACKEND_PORT" "$LOCAL_STATE_DIR/backend.pid" || true
say "Testing pipeline stopped."
umst_pause_if_requested
