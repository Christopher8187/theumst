#!/usr/bin/env bash
set -euo pipefail
cat <<'EOF'
UMST Docker scripts

Local hot-reload testing:
  dev/sh/initialize_local.sh
  dev/sh/activate_local_server.sh
  dev/sh/check_local_server.sh
  dev/sh/logs_local_server.sh
  dev/sh/stop_local_server.sh

Deployment-style local test with nginx:
  dev/sh/activate_deploy_stack.sh
  dev/sh/check_deploy_stack.sh
  dev/sh/logs_deploy_stack.sh
  dev/sh/stop_deploy_stack.sh

Remote Docker deployment:
  dev/sh/initialize_remote_server.sh
  dev/sh/upload_all_to_server.sh
  dev/sh/activate_remote_server.sh
  dev/sh/check_remote_server.sh

Main local URLs:
  http://localhost:5173
  http://localhost:5174/dashboard/profile/
  http://localhost:8000

Nginx deployment-style URL:
  http://localhost:8080
EOF
