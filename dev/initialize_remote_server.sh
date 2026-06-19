#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/load_env.sh"
trap 'say "Remote server initialization failed."' ERR

say "Initializing remote server."
echo "Target: $REMOTE"
echo "Root:   $REMOTE_ROOT"
echo

ssh -i "$KEY" "$REMOTE" "echo SSH OK && $SUDO true"
ssh -i "$KEY" "$REMOTE" "$SUDO apt update && $SUDO apt install -y nginx certbot ufw curl python3 python3-venv python3-pip postgresql postgresql-contrib"
ssh -i "$KEY" "$REMOTE" "curl -fsSL https://deb.nodesource.com/setup_22.x -o /tmp/nodesource.sh && $SUDO bash /tmp/nodesource.sh && $SUDO apt install -y nodejs"
ssh -i "$KEY" "$REMOTE" "$SUDO mkdir -p $REMOTE_ROOT $REMOTE_BACKEND $REMOTE_WEBPAGE $REMOTE_DASHBOARD && $SUDO chown -R $SSH_USER:$NGINX_USER $REMOTE_ROOT && $SUDO chmod 755 /var /var/www"
ssh -i "$KEY" "$REMOTE" "$SUDO -u postgres psql -c \"ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';\" && ($SUDO -u postgres psql -tc \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\" | grep -q 1 || $SUDO -u postgres createdb -O $DB_USER $DB_NAME)"
ssh -i "$KEY" "$REMOTE" "cd $REMOTE_BACKEND && python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip"
ssh -i "$KEY" "$REMOTE" "$SUDO systemctl enable nginx && $SUDO ufw allow OpenSSH && $SUDO ufw allow 'Nginx Full' && $SUDO ufw --force enable"

say "Remote server initialized."
umst_pause_if_requested
