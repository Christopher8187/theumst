#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"
require_docker

echo "Building local Docker images..."
local_compose build

echo "Local Docker setup is ready."
echo "Start it with: dev/sh/activate_local_server.sh"
