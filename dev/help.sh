#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cat <<HELP
UMST shell scripts

Local Linux/Windows-Git-Bash commands:
  dev/initialize_local.sh
  dev/activate_local_nginx_server.sh
  dev/check_local_nginx_server.sh
  dev/stop_local_nginx_server.sh
  dev/build_dashboard_local.sh   # builds webpage and dashboard Vue apps

Remote commands, using REMOTE_SERVER=COM or CN from .env:
  dev/initialize_remote_server.sh
  dev/upload_all_to_server.sh
  dev/activate_remote_nginx_server.sh
  dev/check_remote_nginx_server.sh
  dev/renew_certificates.sh
  dev/give_server_permissions.sh
  dev/stop_remote_nginx_server.sh
  dev/open_remote_terminal.sh

Linux setup example:
  cd /home/christopher/Desktop/theumst
  chmod +x dev/*.sh
  dev/initialize_local.sh
  dev/activate_local_nginx_server.sh

Windows setup example:
  Run these from Git Bash or WSL, not cmd.exe:
  chmod +x dev/*.sh
  dev/initialize_local.sh
HELP
