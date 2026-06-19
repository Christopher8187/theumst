#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$SCRIPT_DIR/load_env.sh"
trap 'say "Remote activation failed."' ERR

SERVICE_FILE="$(mktemp 2>/dev/null || mktemp -t "$BACKEND_SERVICE.service")"
ENV_FILE="$(mktemp 2>/dev/null || mktemp -t "$BACKEND_SERVICE.env")"
cleanup() { rm -f "$SERVICE_FILE" "$ENV_FILE"; }
trap cleanup EXIT

say "Activating remote server."

ssh -i "$KEY" "$REMOTE" "mkdir -p $REMOTE_ROOT/config $REMOTE_BACKEND"
scp -i "$KEY" "$ROOT/config/$NGINX_CONF" "$REMOTE:$REMOTE_ROOT/config/$NGINX_CONF"

cat > "$ENV_FILE" <<ENV
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
SESSION_DAYS=7
SERVER=$SERVER
LOCAL_STORAGE_DIR=__AUTO__
ENV

cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=UMST backend
After=network.target postgresql.service

[Service]
User=$SSH_USER
WorkingDirectory=$REMOTE_BACKEND
EnvironmentFile=/etc/$BACKEND_SERVICE.env
ExecStart=$REMOTE_BACKEND/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port $BACKEND_PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

scp -i "$KEY" "$ENV_FILE" "$REMOTE:/tmp/$BACKEND_SERVICE.env"
scp -i "$KEY" "$SERVICE_FILE" "$REMOTE:/tmp/$BACKEND_SERVICE.service"
ssh -i "$KEY" "$REMOTE" "cd $REMOTE_BACKEND && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
ssh -i "$KEY" "$REMOTE" "cd $REMOTE_WEBPAGE && npm install && (chmod +x node_modules/.bin/* 2>/dev/null || true) && npm run build && cd $REMOTE_DASHBOARD && npm install && (chmod +x node_modules/.bin/* 2>/dev/null || true) && npm run build"
ssh -i "$KEY" "$REMOTE" "PGPASSWORD=$(umst_shell_quote "$DB_PASSWORD") psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f $REMOTE_ROOT/backend/sql/schema.sql"
ssh -i "$KEY" "$REMOTE" "$SUDO mv /tmp/$BACKEND_SERVICE.env /etc/$BACKEND_SERVICE.env && $SUDO chmod 600 /etc/$BACKEND_SERVICE.env && $SUDO mv /tmp/$BACKEND_SERVICE.service /etc/systemd/system/$BACKEND_SERVICE.service && $SUDO systemctl daemon-reload && $SUDO systemctl enable --now $BACKEND_SERVICE && $SUDO systemctl restart $BACKEND_SERVICE"
ssh -i "$KEY" "$REMOTE" "$SUDO cp $REMOTE_ROOT/config/$NGINX_CONF /etc/nginx/sites-available/$NGINX_SITE && $SUDO ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/$NGINX_SITE && $SUDO rm -f /etc/nginx/sites-enabled/default && $SUDO nginx -t && $SUDO systemctl enable nginx && $SUDO systemctl reload-or-restart nginx"

say "Remote server is active."
echo "Open: $REMOTE_URL"
umst_pause_if_requested
