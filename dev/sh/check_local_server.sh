#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"
require_docker

echo "Docker containers:"
local_compose ps

echo
echo "FastAPI health:"
if command -v curl >/dev/null 2>&1; then
    curl -fsS http://localhost:8000/health || true
    echo
else
    echo "curl is not installed; open http://localhost:8000/health in a browser."
fi
