#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"
require_docker

echo "Starting deployment-style Docker stack with nginx..."
deploy_compose up --build -d

echo
echo "Open: http://localhost:${HTTP_PORT:-8080}"
echo "Nginx is the public entry point; FastAPI serves the built Vue apps behind it."
