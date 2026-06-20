#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"
require_docker

echo "Deployment containers:"
deploy_compose ps

echo
echo "Nginx health path:"
if command -v curl >/dev/null 2>&1; then
    curl -fsS "http://localhost:${HTTP_PORT:-8080}/health" || true
    echo
else
    echo "Open http://localhost:${HTTP_PORT:-8080}/health in a browser."
fi
