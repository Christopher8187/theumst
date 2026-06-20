#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
ENV_FILE="$ROOT/.env"
LOCAL_COMPOSE="$ROOT/docker/compose.local.yml"
DEPLOY_COMPOSE="$ROOT/docker/compose.deploy.yml"

load_env() {
    if [ -f "$ENV_FILE" ]; then
        set -a
        # shellcheck disable=SC1090
        . "$ENV_FILE"
        set +a
    fi

    SERVER="${SERVER:-LOCAL}"
    REMOTE_SERVER="${REMOTE_SERVER:-COM}"
    HTTP_PORT="${HTTP_PORT:-8080}"
    SSH_KEY_DIR="${SSH_KEY_DIR:-$HOME/.ssh}"
    [ "$SSH_KEY_DIR" = "__AUTO__" ] && SSH_KEY_DIR="$HOME/.ssh"
}

show_env() {
    load_env
    cat <<INFO
Project root:     $ROOT
Environment file: $ENV_FILE
SERVER:           $SERVER
REMOTE_SERVER:    $REMOTE_SERVER
HTTP_PORT:        $HTTP_PORT

Local URLs:
  Webpage:   http://localhost:5173
  Dashboard: http://localhost:5174/dashboard/profile/
  FastAPI:   http://localhost:8000
  Nginx:     http://localhost:$HTTP_PORT
INFO
}

pause_if_clicked() {
    if [ -t 0 ]; then
        printf '\nPress Enter to close...'
        read -r _ || true
    fi
}

choose() {
    prompt="$1"
    default="$2"
    printf "%s [%s]: " "$prompt" "$default"
    read -r answer || true
    printf '%s' "${answer:-$default}"
}

compose() {
    if docker compose version >/dev/null 2>&1; then
        docker compose "$@"
    elif command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        echo "Docker Compose is missing. Install Docker Desktop or the Docker Compose plugin." >&2
        exit 1
    fi
}

need_docker() {
    command -v docker >/dev/null 2>&1 || { echo "Docker is missing." >&2; exit 1; }
    docker info >/dev/null 2>&1 || { echo "Docker is installed, but it is not running." >&2; exit 1; }
}

local_compose() { (cd "$ROOT" && compose -f "$LOCAL_COMPOSE" "$@"); }
deploy_compose() { (cd "$ROOT" && compose -f "$DEPLOY_COMPOSE" "$@"); }

open_local_urls() {
    cat <<URLS

Open:
  Main webpage: http://localhost:5173
  Dashboard:    http://localhost:5174/dashboard/profile/
  FastAPI:      http://localhost:8000
URLS
}

open_deploy_url() {
    echo
    echo "Open: http://localhost:${HTTP_PORT:-8080}"
}

health_url() {
    url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS "$url" || true
        echo
    else
        echo "curl is not installed; open $url in a browser."
    fi
}

upper() { printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; }
remote_setting() { eval "printf '%s' \"\${$1:-}\""; }

remote_context() {
    load_env
    TARGET_SERVER="$(upper "${1:-${TARGET_SERVER:-$REMOTE_SERVER}}")"
    KEY_NAME="$(remote_setting "SSH_KEY_${TARGET_SERVER}")"
    SSH_USER="$(remote_setting "SSH_USER_${TARGET_SERVER}")"
    SSH_HOST="$(remote_setting "SSH_HOST_${TARGET_SERVER}")"
    REMOTE_ROOT="$(remote_setting "REMOTE_ROOT_${TARGET_SERVER}")"
    REMOTE_URL="$(remote_setting "REMOTE_URL_${TARGET_SERVER}")"
    DOMAIN="$(remote_setting "DOMAIN_${TARGET_SERVER}")"
    CERT_NAME="$(remote_setting "CERT_${TARGET_SERVER}")"
    CERT_MODE="$(remote_setting "CERT_MODE_${TARGET_SERVER}")"
    SUDO_PASSWORD="$(remote_setting "SUDO_PASSWORD_${TARGET_SERVER}")"
    SSH_KEY_DIR="${SSH_KEY_DIR:-$HOME/.ssh}"
    [ "$SSH_KEY_DIR" = "__AUTO__" ] && SSH_KEY_DIR="$HOME/.ssh"
    KEY="$SSH_KEY_DIR/$KEY_NAME"
    REMOTE="$SSH_USER@$SSH_HOST"

    [ -n "$KEY_NAME$SSH_USER$SSH_HOST" ] || { echo "Missing SSH settings for $TARGET_SERVER in .env" >&2; exit 1; }
    [ -f "$KEY" ] || { echo "Missing SSH key: $KEY" >&2; exit 1; }
}

remote_sudo() {
    if [ -n "${SUDO_PASSWORD:-}" ]; then
        printf "printf '%%s\\n' '%s' | sudo -S -p ''" "$SUDO_PASSWORD"
    else
        printf "sudo"
    fi
}

pick_server() {
    default="${1:-${REMOTE_SERVER:-COM}}"
    server="$(choose "Target server COM or CN" "$default")"
    upper "$server"
}

remote_setup() {
    remote_context "$1"
    SUDO="$(remote_sudo)"
    echo "Installing/updating Docker and certbot on $REMOTE..."
    ssh -i "$KEY" "$REMOTE" "$SUDO apt update && $SUDO apt install -y ca-certificates curl gnupg rsync certbot && curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && $SUDO sh /tmp/get-docker.sh && $SUDO usermod -aG docker '$SSH_USER'"
    echo "Remote setup is ready. Reconnect to the server if Docker group permissions do not refresh."
}

remote_permissions() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; exit 1; }
    SUDO="$(remote_sudo)"
    echo "Fixing permissions on $REMOTE:$REMOTE_ROOT..."
    ssh -i "$KEY" "$REMOTE" "mkdir -p '$REMOTE_ROOT' && $SUDO chown -R '$SSH_USER:$SSH_USER' '$REMOTE_ROOT' && chmod -R u+rwX '$REMOTE_ROOT' && $SUDO usermod -aG docker '$SSH_USER' || true"
    echo "Permissions updated. Reconnect to the server if Docker group membership changed."
}

remote_upload() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; exit 1; }
    STAGE="$(mktemp -d 2>/dev/null || mktemp -d -t theumst_upload)"
    trap 'rm -rf "$STAGE"' RETURN EXIT

    echo "Preparing upload folder..."
    (
        cd "$ROOT"
        tar \
            --exclude='./.git' \
            --exclude='./.local' \
            --exclude='./backend/python/.venv' \
            --exclude='./frontend/webpage/node_modules' \
            --exclude='./frontend/webpage/dist' \
            --exclude='./frontend/dashboard/node_modules' \
            --exclude='./frontend/dashboard/dist' \
            -cf - . | (cd "$STAGE" && tar -xf -)
    )

    echo "Uploading to $REMOTE:$REMOTE_ROOT..."
    ssh -i "$KEY" "$REMOTE" "mkdir -p '$REMOTE_ROOT'"
    scp -i "$KEY" -r "$STAGE"/. "$REMOTE:$REMOTE_ROOT/"
}

remote_start() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; exit 1; }
    echo "Starting Docker deployment on $REMOTE..."
    ssh -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && SERVER='$TARGET_SERVER' docker compose -f docker/compose.deploy.yml up --build -d"
}

remote_stop() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; exit 1; }
    echo "Stopping Docker deployment on $REMOTE..."
    ssh -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && docker compose -f docker/compose.deploy.yml down"
}

remote_check() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; exit 1; }
    echo "Remote containers on $REMOTE:"
    ssh -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && docker compose -f docker/compose.deploy.yml ps"
    [ -n "${REMOTE_URL:-}" ] && echo "URL: $REMOTE_URL"
}

remote_logs() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; exit 1; }
    ssh -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && docker compose -f docker/compose.deploy.yml logs --tail=120"
}

remote_shell() {
    remote_context "$1"
    exec ssh -i "$KEY" "$REMOTE"
}

remote_certs() {
    remote_context "$1"
    [ -n "${DOMAIN:-}" ] || { echo "Missing DOMAIN_$TARGET_SERVER in .env" >&2; exit 1; }
    CERT_NAME="${CERT_NAME:-$DOMAIN}"
    CERT_EMAIL="${CERT_EMAIL:-admin@$DOMAIN}"
    SUDO="$(remote_sudo)"

    if [ "${CERT_MODE:-standalone}" = "manual" ]; then
        echo "CERT_MODE_$TARGET_SERVER is manual."
        echo "Suggested command on the server:"
        echo "sudo certbot certonly --manual --preferred-challenges dns -d '$DOMAIN' -d '*.$DOMAIN' --cert-name '$CERT_NAME'"
        echo
        remote_shell "$TARGET_SERVER"
        return
    fi

    echo "Renewing/issuing certificate for $DOMAIN on $REMOTE..."
    ssh -i "$KEY" "$REMOTE" "cd '${REMOTE_ROOT:-.}' 2>/dev/null || true; docker compose -f docker/compose.deploy.yml stop nginx >/dev/null 2>&1 || true; $SUDO apt update && $SUDO apt install -y certbot; $SUDO certbot certonly --standalone --non-interactive --agree-tos -m '$CERT_EMAIL' --cert-name '$CERT_NAME' -d '$DOMAIN' -d 'www.$DOMAIN' || $SUDO certbot renew; cd '${REMOTE_ROOT:-.}' 2>/dev/null && docker compose -f docker/compose.deploy.yml up -d nginx >/dev/null 2>&1 || true"
    echo "Certificate command finished."
}

remote_full_deploy() {
    remote_permissions "$1"
    remote_upload "$1"
    remote_start "$1"
    remote_check "$1"
}
