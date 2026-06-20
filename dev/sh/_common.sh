#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
ENV_FILE="$ROOT/.env"
LOCAL_COMPOSE="$ROOT/compose.local.yml"
DEPLOY_COMPOSE="$ROOT/compose.deploy.yml"

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
    if [ "$SSH_KEY_DIR" = "__AUTO__" ]; then
        SSH_KEY_DIR="$HOME/.ssh"
    fi

    return 0
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
    # Keep double-clicked terminal windows open long enough to read errors.
    if [ "${NO_PAUSE:-}" = "1" ]; then
        return 0
    fi

    if [ -t 0 ]; then
        printf '
Press Enter to close...'
        IFS= read -r _ || true
    elif [ -e /dev/tty ]; then
        if printf '
Press Enter to close...' > /dev/tty 2>/dev/null; then
            IFS= read -r _ < /dev/tty 2>/dev/null || true
        fi
    fi
}

on_error() {
    status="${3:-$?}"
    line="${1:-?}"
    command="${2:-unknown}"
    trap - ERR

    echo >&2
    echo "Script failed." >&2
    echo "  Exit code: $status" >&2
    echo "  Line:      $line" >&2
    echo "  Command:   $command" >&2
    echo >&2
    echo "Most common Linux causes:" >&2
    echo "  - Docker service is not running." >&2
    echo "  - Your Linux user is not in the docker group yet." >&2
    echo "  - Some project files were created by sudo/root earlier." >&2
    echo "  - A port is already occupied, often 5432, 8000, 5173, 5174, or 8080." >&2
    echo >&2
    echo "Useful repair commands from the project root:" >&2
    echo '  sudo chown -R "$USER:$USER" .' >&2
    echo '  chmod +x dev/sh/*.sh' >&2
    echo '  sudo systemctl enable --now docker' >&2
    echo '  sudo usermod -aG docker "$USER"' >&2
    echo '  newgrp docker' >&2
    echo '  docker run --rm hello-world' >&2

    pause_if_clicked
    exit "$status"
}


choose() {
    prompt="$1"
    default="$2"

    # Print prompts to stderr, not stdout, because callers capture stdout:
    # choice="$(choose ...)". Only the selected value goes to stdout.
    printf "%s [%s]: " "$prompt" "$default" >&2
    IFS= read -r answer || true
    printf '%s' "${answer:-$default}"
}



compose() {
    if docker compose version >/dev/null 2>&1; then
        docker compose "$@"
    elif command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        echo "Docker Compose is missing. Install Docker Desktop or the Docker Compose plugin." >&2
        return 1
    fi
}

need_docker() {
    command -v docker >/dev/null 2>&1 || {
        echo "Docker is missing. Install Docker Engine/Desktop first." >&2
        return 1
    }

    if docker info >/dev/null 2>&1; then
        return 0
    fi

    docker_error="$(docker info 2>&1 >/dev/null || true)"

    cat >&2 <<HELP
Docker is installed, but this Linux user cannot talk to Docker.

Docker said:
${docker_error:-  docker info failed}

Fix it from the project root:
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
  newgrp docker
  docker run --rm hello-world

If Docker was previously run with sudo inside this project, also run:
  sudo chown -R "$USER:$USER" .
HELP
    return 1
}


fix_local_script_permissions() {
    chmod +x "$SCRIPT_DIR"/*.sh
    echo "Made dev/sh/*.sh executable."
}

fix_local_project_permissions() {
    echo "Fixing ownership and writable folders under: $ROOT"
    sudo chown -R "$USER:$USER" "$ROOT"
    find "$ROOT/dev/sh" -type f -name '*.sh' -exec chmod u+x {} \;
    find "$ROOT" -type d -exec chmod u+rwx {} \;
    find "$ROOT" -type f -exec chmod u+rw {} \;
    echo "Local project files now belong to $USER and are writable by $USER."
}

fix_local_docker_group() {
    command -v docker >/dev/null 2>&1 || { echo "Docker is missing." >&2; return 1; }
    sudo systemctl enable --now docker 2>/dev/null || true
    if groups "$USER" | tr ' ' '\n' | grep -qx docker; then
        echo "$USER is already in the docker group."
    else
        sudo usermod -aG docker "$USER"
        echo "Added $USER to the docker group."
    fi
    cat <<'HELP'

Refresh your group membership with one of these:
  newgrp docker

or fully log out and log back in. Then test:
  docker run --rm hello-world
HELP
}

test_local_docker_permissions() {
    command -v docker >/dev/null 2>&1 || { echo "Docker is missing." >&2; return 1; }
    docker info >/dev/null
    docker compose version >/dev/null 2>&1 || docker-compose version >/dev/null
    docker run --rm hello-world
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

    [ -n "$KEY_NAME$SSH_USER$SSH_HOST" ] || { echo "Missing SSH settings for $TARGET_SERVER in .env" >&2; return 1; }
    [ -f "$KEY" ] || { echo "Missing SSH key: $KEY" >&2; return 1; }
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
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    SUDO="$(remote_sudo)"
    echo "Fixing permissions on $REMOTE:$REMOTE_ROOT..."
    ssh -i "$KEY" "$REMOTE" "mkdir -p '$REMOTE_ROOT' && $SUDO chown -R '$SSH_USER:$SSH_USER' '$REMOTE_ROOT' && chmod -R u+rwX '$REMOTE_ROOT' && $SUDO usermod -aG docker '$SSH_USER' || true"
    echo "Permissions updated. Reconnect to the server if Docker group membership changed."
}

remote_upload() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
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
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    echo "Starting Docker deployment on $REMOTE..."
    ssh -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && SERVER='$TARGET_SERVER' docker compose -f compose.deploy.yml up --build -d"
}

remote_stop() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    echo "Stopping Docker deployment on $REMOTE..."
    ssh -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && docker compose -f compose.deploy.yml down"
}

remote_check() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    echo "Remote containers on $REMOTE:"
    ssh -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && docker compose -f compose.deploy.yml ps"
    [ -n "${REMOTE_URL:-}" ] && echo "URL: $REMOTE_URL"
}

remote_logs() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    ssh -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && docker compose -f compose.deploy.yml logs --tail=120"
}

remote_shell() {
    remote_context "$1"
    exec ssh -i "$KEY" "$REMOTE"
}

remote_certs() {
    remote_context "$1"
    [ -n "${DOMAIN:-}" ] || { echo "Missing DOMAIN_$TARGET_SERVER in .env" >&2; return 1; }
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
    ssh -i "$KEY" "$REMOTE" "cd '${REMOTE_ROOT:-.}' 2>/dev/null || true; docker compose -f compose.deploy.yml stop nginx >/dev/null 2>&1 || true; $SUDO apt update && $SUDO apt install -y certbot; $SUDO certbot certonly --standalone --non-interactive --agree-tos -m '$CERT_EMAIL' --cert-name '$CERT_NAME' -d '$DOMAIN' -d 'www.$DOMAIN' || $SUDO certbot renew; cd '${REMOTE_ROOT:-.}' 2>/dev/null && docker compose -f compose.deploy.yml up -d nginx >/dev/null 2>&1 || true"
    echo "Certificate command finished."
}

remote_full_deploy() {
    remote_permissions "$1"
    remote_upload "$1"
    remote_start "$1"
    remote_check "$1"
}
