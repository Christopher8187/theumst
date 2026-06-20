#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"
require_docker

echo "Starting local Docker stack..."
local_compose up --build -d

echo
echo "Open these URLs:"
echo "  Main webpage: http://localhost:5173"
echo "  Dashboard:    http://localhost:5174/dashboard/profile/"
echo "  FastAPI:      http://localhost:8000"
echo
echo "Use dev/sh/check_local_server.sh to check status."
