#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
ENV_FILE="$ROOT/.env"
LOCAL_COMPOSE="$ROOT/compose.local.yml"
DEPLOY_COMPOSE="$ROOT/compose.deploy.yml"
SSH_OPTIONS=(-o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=4)

normalize_host_path() {
    path_value="${1:-}"
    [ -n "$path_value" ] || return 1

    case "$path_value" in
        [A-Za-z]:\\*|[A-Za-z]:/*)
            if command -v wslpath >/dev/null 2>&1; then
                wslpath -u "$path_value"
                return
            fi
            if command -v cygpath >/dev/null 2>&1; then
                cygpath -u "$path_value"
                return
            fi

            drive="$(printf '%s' "${path_value%%:*}" | tr '[:upper:]' '[:lower:]')"
            remainder="${path_value#*:}"
            remainder="$(printf '%s' "$remainder" | tr '\\' '/')"
            remainder="${remainder#/}"
            if grep -qi microsoft /proc/version 2>/dev/null; then
                printf '/mnt/%s/%s\n' "$drive" "$remainder"
            else
                printf '/%s/%s\n' "$drive" "$remainder"
            fi
            ;;
        *)
            printf '%s\n' "$path_value"
            ;;
    esac
}

resolve_ssh_key_dir() {
    configured="${SSH_KEY_DIR:-}"
    if [ -n "$configured" ] && [ "$configured" != "__AUTO__" ]; then
        normalize_host_path "$configured"
        return
    fi

    # The Windows wrappers export this explicitly. Under WSL, WSLENV translates
    # it to /mnt/c/...; under Git Bash, normalize_host_path uses cygpath.
    if [ -n "${THEUMST_SSH_KEY_DIR:-}" ]; then
        normalize_host_path "$THEUMST_SSH_KEY_DIR"
        return
    fi

    # Support launching the shell script directly from a Windows-aware shell.
    if [ -n "${USERPROFILE:-}" ]; then
        normalize_host_path "${USERPROFILE%[\\/]}/.ssh"
        return
    fi

    printf '%s/.ssh\n' "$HOME"
}

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
    SSH_KEY_DIR="$(resolve_ssh_key_dir)"

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


local_build() { need_docker; local_compose build; }
local_start() { need_docker; local_compose up --build -d --remove-orphans; open_local_urls; }
local_stop() { need_docker; local_compose down; }
local_reset() { need_docker; local_compose down -v; }
local_logs() { need_docker; local_compose logs -f; }
local_check() {
    need_docker
    local_compose ps
    echo
    health_url http://127.0.0.1:8000/health
    health_url http://127.0.0.1:8000/health/db
    health_url http://127.0.0.1:8000/health/assets
}

deploy_build() { need_docker; deploy_compose build; }
deploy_start() { need_docker; deploy_compose up --build -d --remove-orphans; open_deploy_url; }
deploy_stop() { need_docker; deploy_compose down; }
deploy_reset() { need_docker; deploy_compose down -v; }
deploy_logs() { need_docker; deploy_compose logs -f; }
deploy_check() {
    need_docker
    deploy_compose ps
    echo
    health_url "http://127.0.0.1:${HTTP_PORT:-8080}/health"
    health_url "http://127.0.0.1:${HTTP_PORT:-8080}/health/db"
    health_url "http://127.0.0.1:${HTTP_PORT:-8080}/health/assets"
}

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
    NGINX_SITE="$(remote_setting "NGINX_SITE_${TARGET_SERVER}")"
    NGINX_CONF="$(remote_setting "NGINX_CONF_${TARGET_SERVER}")"
    SUDO_PASSWORD="$(remote_setting "SUDO_PASSWORD_${TARGET_SERVER}")"
    SSH_KEY_DIR="$(resolve_ssh_key_dir)"
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
    echo "Preparing Docker, Nginx, Certbot, curl, and rsync on $REMOTE..."
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "$SUDO apt-get update && $SUDO apt-get install -y ca-certificates curl gnupg rsync nginx certbot && if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && $SUDO sh /tmp/get-docker.sh; fi && $SUDO systemctl enable --now docker && $SUDO usermod -aG docker '$SSH_USER' && if command -v ufw >/dev/null 2>&1; then $SUDO ufw allow OpenSSH && $SUDO ufw allow 80/tcp && $SUDO ufw allow 443/tcp; fi"
}

remote_permissions() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    SUDO="$(remote_sudo)"
    echo "Fixing permissions on $REMOTE:$REMOTE_ROOT..."
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "mkdir -p '$REMOTE_ROOT' && $SUDO chown -R '$SSH_USER:$SSH_USER' '$REMOTE_ROOT' && chmod -R u+rwX '$REMOTE_ROOT' && $SUDO usermod -aG docker '$SSH_USER' || true"
    echo "Permissions updated. Reconnect to the server if Docker group membership changed."
}

build_remote_env() {
    remote_context "$1"
    target_env="$2"
    umask 077

    cat > "$target_env" <<EOF
SERVER=$TARGET_SERVER
HTTP_PORT=${HTTP_PORT:-8080}
SESSION_DAYS=${SESSION_DAYS:-7}
COOKIE_SECURE=true
CORS_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}

DB_NAME=${DB_NAME:-theumst}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres}
DB_HOST=db
DB_PORT=5432

QDRANT_API_KEY=${QDRANT_API_KEY}
QDRANT_COLLECTION=${QDRANT_COLLECTION:-knowledge-semantic-v1}
QDRANT_VECTOR_SIZE=${QDRANT_VECTOR_SIZE:-1536}
QDRANT_DISTANCE=${QDRANT_DISTANCE:-cosine}
QDRANT_VECTORS_ON_DISK=${QDRANT_VECTORS_ON_DISK:-false}

EMBEDDING_API_URL=${EMBEDDING_API_URL:-}
EMBEDDING_API_KEY=${EMBEDDING_API_KEY:-}
EMBEDDING_MODEL=${EMBEDDING_MODEL:-}
EOF

    if [ "$TARGET_SERVER" = "COM" ]; then
        cat >> "$target_env" <<EOF
DO_SPACES_BUCKET=${DO_SPACES_BUCKET}
DO_SPACES_REGION=${DO_SPACES_REGION}
DO_SPACES_ENDPOINT=${DO_SPACES_ENDPOINT}
DO_SPACES_ACCESS_KEY_ID=${DO_SPACES_ACCESS_KEY_ID}
DO_SPACES_SECRET_ACCESS_KEY=${DO_SPACES_SECRET_ACCESS_KEY}
EOF
    elif [ "$TARGET_SERVER" = "CN" ]; then
        cat >> "$target_env" <<EOF
ALIYUN_OSS_BUCKET=${ALIYUN_OSS_BUCKET}
ALIYUN_OSS_ENDPOINT=${ALIYUN_OSS_ENDPOINT}
ALIYUN_OSS_ACCESS_KEY_ID=${ALIYUN_OSS_ACCESS_KEY_ID}
ALIYUN_OSS_SECRET_ACCESS_KEY=${ALIYUN_OSS_SECRET_ACCESS_KEY}
EOF
    else
        echo "Remote target must be COM or CN" >&2
        return 1
    fi
}

remote_upload() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    STAGE="$(mktemp -d 2>/dev/null || mktemp -d -t theumst_upload)"
    REMOTE_ENV="$(mktemp 2>/dev/null || mktemp -t theumst_env)"
    trap 'rm -rf "$STAGE" "$REMOTE_ENV"' RETURN EXIT

    echo "Preparing application source for $TARGET_SERVER..."
    (
        cd "$ROOT"
        tar \
            --exclude='./.git' \
            --exclude='./.env' \
            --exclude='./SECRET_ROTATION_NOTES.md' \
            --exclude='./.local' \
            --exclude='./backend/python/.venv' \
            --exclude='./frontend/webpage/node_modules' \
            --exclude='./frontend/webpage/dist' \
            --exclude='./frontend/dashboard/node_modules' \
            --exclude='./frontend/dashboard/dist' \
            -cf - . | (cd "$STAGE" && tar -xf -)
    )
    build_remote_env "$TARGET_SERVER" "$REMOTE_ENV"

    echo "Uploading source and target-only secrets to $REMOTE:$REMOTE_ROOT..."
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "mkdir -p '$REMOTE_ROOT'"
    scp "${SSH_OPTIONS[@]}" -i "$KEY" -r "$STAGE"/. "$REMOTE:$REMOTE_ROOT/"
    scp "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE_ENV" "$REMOTE:$REMOTE_ROOT/.env"
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "chmod 600 '$REMOTE_ROOT/.env'"
}

remote_start() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    SUDO="$(remote_sudo)"
    echo "Building and starting the production stack on $REMOTE..."
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && $SUDO docker compose --env-file .env -f compose.deploy.yml up --build -d --remove-orphans"
}

remote_stop() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    echo "Stopping Docker deployment on $REMOTE..."
    SUDO="$(remote_sudo)"
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && $SUDO docker compose --env-file .env -f compose.deploy.yml down"
}

remote_check() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    echo "Remote containers on $REMOTE:"
    SUDO="$(remote_sudo)"
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && $SUDO docker compose --env-file .env -f compose.deploy.yml ps"
    [ -n "${REMOTE_URL:-}" ] && echo "URL: $REMOTE_URL"
}

remote_logs() {
    remote_context "$1"
    [ -n "$REMOTE_ROOT" ] || { echo "Missing REMOTE_ROOT_$TARGET_SERVER in .env" >&2; return 1; }
    SUDO="$(remote_sudo)"
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "cd '$REMOTE_ROOT' && $SUDO docker compose --env-file .env -f compose.deploy.yml logs --tail=120"
}

remote_shell() {
    remote_context "$1"
    exec ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE"
}

remote_wait_for_application() {
    remote_context "$1"
    echo "Waiting for the application health endpoint on $REMOTE..."
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "for attempt in \$(seq 1 60); do if curl -fsS 'http://127.0.0.1:${HTTP_PORT:-8080}/health/db' >/dev/null; then exit 0; fi; sleep 5; done; echo 'Application did not become healthy' >&2; exit 1"
}

remote_certs() {
    remote_context "$1"
    [ -n "$DOMAIN" ] || { echo "Missing DOMAIN_$TARGET_SERVER in .env" >&2; return 1; }
    CERT_NAME="${CERT_NAME:-$DOMAIN}"
    CERT_EMAIL="${CERT_EMAIL:-admin@$DOMAIN}"
    SUDO="$(remote_sudo)"

    if ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "$SUDO test -s '/etc/letsencrypt/live/$CERT_NAME/fullchain.pem' && $SUDO test -s '/etc/letsencrypt/live/$CERT_NAME/privkey.pem'"; then
        echo "Certificate $CERT_NAME already exists on $REMOTE."
        return 0
    fi

    if [ "${CERT_MODE:-standalone}" = "manual" ]; then
        echo "Starting the interactive DNS certificate flow for $DOMAIN."
        echo "Certbot will display the exact TXT record name and value."
        echo "Create that DNS record, wait until it resolves, then press Enter in Certbot."
        if [ -n "${SUDO_PASSWORD:-}" ]; then
            INTERACTIVE_SUDO="printf '%s\n' '$SUDO_PASSWORD' | sudo -S -p '' true && sudo"
        else
            INTERACTIVE_SUDO="sudo"
        fi
        ssh -tt "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "$INTERACTIVE_SUDO certbot certonly --manual --preferred-challenges dns --agree-tos --manual-public-ip-logging-ok -m '$CERT_EMAIL' --cert-name '$CERT_NAME' -d '$DOMAIN' -d '*.$DOMAIN'"
        return 0
    fi

    echo "Issuing a standalone Let's Encrypt certificate for $DOMAIN..."
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "$SUDO systemctl stop nginx >/dev/null 2>&1 || true; $SUDO certbot certonly --standalone --non-interactive --agree-tos -m '$CERT_EMAIL' --cert-name '$CERT_NAME' -d '$DOMAIN' -d 'www.$DOMAIN'"
}

remote_install_nginx_site() {
    remote_context "$1"
    [ -n "$NGINX_CONF" ] || { echo "Missing NGINX_CONF_$TARGET_SERVER in .env" >&2; return 1; }
    [ -n "$NGINX_SITE" ] || NGINX_SITE="$DOMAIN"
    SUDO="$(remote_sudo)"

    echo "Installing host Nginx site $NGINX_SITE on $REMOTE..."
    scp "${SSH_OPTIONS[@]}" -i "$KEY" "$ROOT/config/$NGINX_CONF" "$REMOTE:/tmp/$NGINX_CONF"
    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "$SUDO cp '/tmp/$NGINX_CONF' '/etc/nginx/sites-available/$NGINX_SITE' && $SUDO ln -sfn '/etc/nginx/sites-available/$NGINX_SITE' '/etc/nginx/sites-enabled/$NGINX_SITE' && $SUDO rm -f /etc/nginx/sites-enabled/default && $SUDO nginx -t && $SUDO systemctl enable --now nginx && $SUDO systemctl restart nginx"

    if [ "${CERT_MODE:-standalone}" = "standalone" ]; then
        scp "${SSH_OPTIONS[@]}" -i "$KEY"             "$ROOT/config/certbot-renewal-pre.sh"             "$ROOT/config/certbot-renewal-post.sh"             "$REMOTE:/tmp/"
        ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" "$SUDO mkdir -p /etc/letsencrypt/renewal-hooks/pre /etc/letsencrypt/renewal-hooks/post && $SUDO cp /tmp/certbot-renewal-pre.sh /etc/letsencrypt/renewal-hooks/pre/theumst-nginx && $SUDO cp /tmp/certbot-renewal-post.sh /etc/letsencrypt/renewal-hooks/post/theumst-nginx && $SUDO chmod 755 /etc/letsencrypt/renewal-hooks/pre/theumst-nginx /etc/letsencrypt/renewal-hooks/post/theumst-nginx && $SUDO systemctl enable --now certbot.timer"
    fi
}

remote_external_health() {
    remote_context "$1"
    [ -n "$REMOTE_URL" ] || { echo "Missing REMOTE_URL_$TARGET_SERVER" >&2; return 1; }
    echo "Checking public website: $REMOTE_URL"
    for path in /health /health/db /health/qdrant /health/assets /; do
        curl -fsS --retry 12 --retry-delay 5 --retry-all-errors "$REMOTE_URL$path" >/dev/null
        echo "  OK $path"
    done
}

remote_full_deploy() {
    target="$1"
    remote_setup "$target"
    remote_permissions "$target"
    remote_upload "$target"
    remote_start "$target"
    remote_wait_for_application "$target"
    remote_certs "$target"
    remote_install_nginx_site "$target"
    remote_check "$target"
    remote_external_health "$target"
    echo
    echo "Deployment complete: $REMOTE_URL"
}
