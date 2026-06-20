#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"
require_docker

echo "Stopping deployment-style Docker stack..."
deploy_compose down
