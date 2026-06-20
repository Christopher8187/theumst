#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
LOCAL_COMPOSE="$ROOT/docker/compose.local.yml"
DEPLOY_COMPOSE="$ROOT/docker/compose.deploy.yml"
ENV_FILE="$ROOT/.env"

load_dotenv() {
    [ -f "$ENV_FILE" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in ''|'#'*) continue ;; esac
        case "$line" in *=*) ;; *) continue ;; esac
        key="${line%%=*}"
        value="${line#*=}"
        case "$key" in *[!A-Za-z0-9_]*|[0-9]*) continue ;; esac
        export "$key=$value"
    done < "$ENV_FILE"
}

compose() {
    if docker compose version >/dev/null 2>&1; then
        docker compose "$@"
    elif command -v docker-compose >/dev/null 2>&1; then
        docker-compose "$@"
    else
        echo "Docker Compose is missing. Install Docker Desktop or the docker compose plugin." >&2
        exit 1
    fi
}

local_compose() {
    (cd "$ROOT" && compose -f "$LOCAL_COMPOSE" "$@")
}

deploy_compose() {
    (cd "$ROOT" && compose -f "$DEPLOY_COMPOSE" "$@")
}

require_docker() {
    command -v docker >/dev/null 2>&1 || { echo "Docker is missing." >&2; exit 1; }
    docker info >/dev/null 2>&1 || { echo "Docker is not running." >&2; exit 1; }
}

remote_value() {
    name="$1"
    eval "printf '%s' \"\${$name:-}\""
}

load_dotenv
SERVER="${SERVER:-LOCAL}"
REMOTE_SERVER="${REMOTE_SERVER:-COM}"
TARGET_SERVER="${TARGET_SERVER:-$REMOTE_SERVER}"
TARGET_SERVER="$(printf '%s' "$TARGET_SERVER" | tr '[:lower:]' '[:upper:]')"
