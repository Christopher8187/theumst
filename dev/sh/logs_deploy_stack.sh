#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "$0")/load_env.sh"
require_docker
deploy_compose logs -f
