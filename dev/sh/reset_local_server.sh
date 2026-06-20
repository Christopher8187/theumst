#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"
require_docker

echo "Stopping local Docker stack and deleting local Docker volumes..."
local_compose down -v
