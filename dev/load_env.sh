#!/usr/bin/env bash
# Shared environment loader for the UMST development scripts.
# Source this file from another script:  . "$(dirname "$0")/load_env.sh"

umst_is_windows() {
    case "$(uname -s 2>/dev/null || echo unknown)" in
        MINGW*|MSYS*|CYGWIN*) return 0 ;;
        *) return 1 ;;
    esac
}

umst_to_cmd_path() {
    local value="${1:-}"
    if umst_is_windows && command -v cygpath >/dev/null 2>&1; then
        cygpath -u "$value"
    else
        printf '%s\n' "$value"
    fi
}

umst_to_nginx_path() {
    local value="${1:-}"
    if umst_is_windows && command -v cygpath >/dev/null 2>&1; then
        cygpath -m "$value"
    else
        printf '%s\n' "$value"
    fi
}

umst_shell_quote() {
    printf "'"
    printf '%s' "${1:-}" | sed "s/'/'\\''/g"
    printf "'"
}

umst_pause_if_requested() {
    if [ "${PAUSE_ON_EXIT:-0}" = "1" ]; then
        printf '\nPress Enter to continue...'
        read -r _ || true
    fi
}

say() {
    local message="${1:-}"
    printf '%s\n' "$message"
    if umst_is_windows && command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
            "Add-Type -AssemblyName System.Speech; \$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; \$s.Speak('$message')" >/dev/null 2>&1 || true
    elif command -v spd-say >/dev/null 2>&1; then
        spd-say "$message" >/dev/null 2>&1 || true
    elif command -v say >/dev/null 2>&1; then
        command say "$message" >/dev/null 2>&1 || true
    fi
}

fail() {
    say "${1:-Command failed.}"
    umst_pause_if_requested
    exit 1
}

umst_find_python() {
    if command -v python3 >/dev/null 2>&1; then
        UMST_PYTHON=(python3)
    elif command -v python >/dev/null 2>&1; then
        UMST_PYTHON=(python)
    elif command -v py >/dev/null 2>&1; then
        UMST_PYTHON=(py -3)
    else
        return 1
    fi
}

umst_system_python() {
    umst_find_python || return 1
    "${UMST_PYTHON[@]}" "$@"
}

umst_backend_python() {
    if [ -x "$ROOT/backend/python/.venv/bin/python" ]; then
        printf '%s\n' "$ROOT/backend/python/.venv/bin/python"
    elif [ -x "$ROOT/backend/python/.venv/Scripts/python.exe" ]; then
        printf '%s\n' "$ROOT/backend/python/.venv/Scripts/python.exe"
    else
        return 1
    fi
}

umst_find_npm() {
    if command -v npm >/dev/null 2>&1; then
        UMST_NPM=(npm)
    elif command -v npm.cmd >/dev/null 2>&1; then
        UMST_NPM=(npm.cmd)
    else
        return 1
    fi
}

umst_port_listening() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"
    elif command -v lsof >/dev/null 2>&1; then
        lsof -iTCP:"$port" -sTCP:LISTEN -Pn >/dev/null 2>&1
    elif command -v netstat >/dev/null 2>&1; then
        netstat -ano 2>/dev/null | grep -E "[:.]${port}[[:space:]].*LISTEN" >/dev/null 2>&1
    else
        return 1
    fi
}

umst_stop_process_on_port() {
    local port="$1"
    if [ -f "$LOCAL_STATE_DIR/backend.pid" ]; then
        local pid
        pid="$(cat "$LOCAL_STATE_DIR/backend.pid" 2>/dev/null || true)"
        if [ -n "$pid" ] && kill "$pid" >/dev/null 2>&1; then
            rm -f "$LOCAL_STATE_DIR/backend.pid"
            return 0
        fi
    fi

    if command -v lsof >/dev/null 2>&1; then
        lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | xargs -r kill >/dev/null 2>&1 || true
    elif umst_is_windows && command -v netstat >/dev/null 2>&1 && command -v taskkill >/dev/null 2>&1; then
        netstat -ano | awk -v p=":$port" '$0 ~ p && $0 ~ /LISTEN/ {print $NF}' | while read -r pid; do
            [ -n "$pid" ] && taskkill //PID "$pid" //F >/dev/null 2>&1 || true
        done
    fi
}

umst_load_dotenv() {
    local file="$1"
    [ -f "$file" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in
            ''|'#'*) continue ;;
        esac
        [[ "$line" == *'='* ]] || continue
        local key="${line%%=*}"
        local value="${line#*=}"
        key="$(printf '%s' "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        value="$(printf '%s' "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        case "$value" in
            \"*\") value="${value#\"}"; value="${value%\"}" ;;
            \'*\') value="${value#\'}"; value="${value%\'}" ;;
        esac
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        export "$key=$value"
    done < "$file"
}

UMST_DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
UMST_SCRIPT_ROOT="$(cd "$UMST_DEV_DIR/.." && pwd -P)"
umst_load_dotenv "$UMST_SCRIPT_ROOT/.env"

if [ -n "${PROJECT_ROOT:-}" ] && [ -d "$(umst_to_cmd_path "$PROJECT_ROOT")" ]; then
    ROOT="$(cd "$(umst_to_cmd_path "$PROJECT_ROOT")" && pwd -P)"
else
    ROOT="$UMST_SCRIPT_ROOT"
fi
export ROOT

ENV_FILE="$ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
    printf 'Missing .env at %s\n' "$ENV_FILE" >&2
    return 1 2>/dev/null || exit 1
fi
# Reload the actual project .env when PROJECT_ROOT redirected us.
umst_load_dotenv "$ENV_FILE"

SERVER="${SERVER:-LOCAL}"
SERVER="$(printf '%s' "$SERVER" | tr '[:lower:]' '[:upper:]')"
export SERVER

REMOTE_SERVER="${REMOTE_SERVER:-COM}"
REMOTE_SERVER="$(printf '%s' "$REMOTE_SERVER" | tr '[:lower:]' '[:upper:]')"
export REMOTE_SERVER

LOCAL_URL="${LOCAL_URL:-http://localhost:8080}"
NGINX_USER="${NGINX_USER:-www-data}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
WEBPAGE_PORT="${WEBPAGE_PORT:-5173}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5174}"
BACKEND_SERVICE="${BACKEND_SERVICE:-theumst-backend}"
DB_NAME="${DB_NAME:-theumst}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
CERT_MODE="${CERT_MODE:-standalone}"
WEBPAGE_DIR="$ROOT/frontend/webpage"
DASHBOARD_DIR="$ROOT/frontend/dashboard"
LOCAL_STATE_DIR="$ROOT/.local"
LOCAL_LOG_DIR="$LOCAL_STATE_DIR/logs"
LOCAL_NGINX_PREFIX="$LOCAL_STATE_DIR/nginx"
LOCAL_NGINX_CONF="$LOCAL_NGINX_PREFIX/nginx.conf"
LOCAL_NGINX_TEMPLATE="$ROOT/config/nginx.local.conf"

if [ -z "${LOCAL_STORAGE_DIR:-}" ] || [ "${LOCAL_STORAGE_DIR:-}" = "__AUTO__" ]; then
    LOCAL_STORAGE_DIR="$HOME/theumst_storage"
fi
export LOCAL_URL NGINX_USER BACKEND_PORT WEBPAGE_PORT DASHBOARD_PORT BACKEND_SERVICE DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT WEBPAGE_DIR DASHBOARD_DIR LOCAL_STATE_DIR LOCAL_LOG_DIR LOCAL_NGINX_PREFIX LOCAL_NGINX_CONF LOCAL_NGINX_TEMPLATE LOCAL_STORAGE_DIR

if umst_is_windows; then
    NGINX_PATH="${NGINX_PATH:-C:\\nginx}"
    NGINX_PATH_CMD="$(umst_to_cmd_path "$NGINX_PATH")"
    NGINX_BIN="${NGINX_BIN:-$NGINX_PATH_CMD/nginx.exe}"
else
    NGINX_BIN="${NGINX_BIN:-nginx}"
fi
export NGINX_PATH NGINX_BIN

umst_write_fallback_mime_types() {
    mkdir -p "$LOCAL_NGINX_PREFIX/conf"
    cat > "$LOCAL_NGINX_PREFIX/conf/mime.types" <<'MIME'
types {
    text/html html htm;
    text/css css;
    application/javascript js mjs;
    application/json json;
    image/png png;
    image/jpeg jpg jpeg;
    image/svg+xml svg;
    image/gif gif;
    image/webp webp;
    font/woff woff;
    font/woff2 woff2;
}
MIME
}

umst_local_mime_types_path() {
    if umst_is_windows; then
        local win_mime="$(dirname "$NGINX_BIN")/conf/mime.types"
        if [ -f "$win_mime" ]; then
            umst_to_nginx_path "$win_mime"
            return 0
        fi
    fi
    if [ -f /etc/nginx/mime.types ]; then
        printf '%s\n' /etc/nginx/mime.types
        return 0
    fi
    if [ -f /usr/local/nginx/conf/mime.types ]; then
        printf '%s\n' /usr/local/nginx/conf/mime.types
        return 0
    fi
    umst_write_fallback_mime_types
    umst_to_nginx_path "$LOCAL_NGINX_PREFIX/conf/mime.types"
}

umst_prepare_local_nginx_dirs() {
    # Windows nginx opens its default error log before it fully reads our config,
    # so these default prefix folders must exist even though the generated config
    # writes the real logs to $LOCAL_LOG_DIR.
    mkdir -p         "$LOCAL_STATE_DIR"         "$LOCAL_LOG_DIR"         "$LOCAL_NGINX_PREFIX"         "$LOCAL_NGINX_PREFIX/logs"         "$LOCAL_NGINX_PREFIX/temp/client_body_temp"         "$LOCAL_NGINX_PREFIX/temp/proxy_temp"         "$LOCAL_NGINX_PREFIX/temp/fastcgi_temp"         "$LOCAL_NGINX_PREFIX/temp/uwsgi_temp"         "$LOCAL_NGINX_PREFIX/temp/scgi_temp"         "$LOCAL_NGINX_PREFIX/conf"
}

umst_write_local_nginx_conf() {
    umst_prepare_local_nginx_dirs
    local root_path pid_path access_log error_log mime_types conf_text
    root_path="$(umst_to_nginx_path "$ROOT")"
    pid_path="$(umst_to_nginx_path "$LOCAL_NGINX_PREFIX/nginx.pid")"
    access_log="$(umst_to_nginx_path "$LOCAL_LOG_DIR/nginx.access.log")"
    error_log="$(umst_to_nginx_path "$LOCAL_LOG_DIR/nginx.error.log")"
    mime_types="$(umst_local_mime_types_path)"
    conf_text="$(cat "$LOCAL_NGINX_TEMPLATE")"
    conf_text="${conf_text//__ROOT__/$root_path}"
    conf_text="${conf_text//__PID__/$pid_path}"
    conf_text="${conf_text//__ACCESS_LOG__/$access_log}"
    conf_text="${conf_text//__ERROR_LOG__/$error_log}"
    conf_text="${conf_text//__MIME_TYPES__/$mime_types}"
    printf '%s\n' "$conf_text" > "$LOCAL_NGINX_CONF"
}

umst_nginx() {
    "$NGINX_BIN" -c "$LOCAL_NGINX_CONF" -p "$LOCAL_NGINX_PREFIX/" "$@"
}

# Return early for local-only scripts after all local helpers are available.
if [ "${LOCAL_ONLY:-0}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

TARGET_SERVER="${TARGET_SERVER:-$REMOTE_SERVER}"
TARGET_SERVER="$(printf '%s' "$TARGET_SERVER" | tr '[:lower:]' '[:upper:]')"
if [ "$TARGET_SERVER" != "COM" ] && [ "$TARGET_SERVER" != "CN" ]; then
    printf 'TARGET_SERVER/REMOTE_SERVER must be COM or CN for remote scripts.\n' >&2
    return 1 2>/dev/null || exit 1
fi
SERVER="$TARGET_SERVER"
SERVER_LOWER="$(printf '%s' "$SERVER" | tr '[:upper:]' '[:lower:]')"
export SERVER SERVER_LOWER

umst_var() {
    local name="$1"
    printf '%s' "${!name:-}"
}

SSH_KEY="$(umst_var "SSH_KEY_$SERVER")"
SSH_USER="$(umst_var "SSH_USER_$SERVER")"
SSH_HOST="$(umst_var "SSH_HOST_$SERVER")"
REMOTE_ROOT="$(umst_var "REMOTE_ROOT_$SERVER")"
NGINX_SITE="$(umst_var "NGINX_SITE_$SERVER")"
NGINX_CONF="$(umst_var "NGINX_CONF_$SERVER")"
REMOTE_URL="$(umst_var "REMOTE_URL_$SERVER")"
DOMAIN="$(umst_var "DOMAIN_$SERVER")"
CERT_NAME="$(umst_var "CERT_$SERVER")"
CERT_MODE="$(umst_var "CERT_MODE_$SERVER")"
SUDO_PASSWORD="$(umst_var "SUDO_PASSWORD_$SERVER")"
CERT_MODE="${CERT_MODE:-standalone}"
BACKEND_SERVICE="${BACKEND_SERVICE:-theumst-$SERVER_LOWER-backend}"

for item in SSH_KEY SSH_USER SSH_HOST REMOTE_ROOT NGINX_SITE NGINX_CONF REMOTE_URL DOMAIN CERT_NAME SUDO_PASSWORD; do
    if [ -z "${!item:-}" ]; then
        printf 'Missing %s_%s in .env.\n' "$item" "$SERVER" >&2
        return 1 2>/dev/null || exit 1
    fi
done

if [ -z "${SSH_KEY_DIR:-}" ] || [ "${SSH_KEY_DIR:-}" = "__AUTO__" ]; then
    SSH_KEY_DIR="$HOME/.ssh"
fi
KEY="$(umst_to_cmd_path "$SSH_KEY_DIR/$SSH_KEY")"
REMOTE="$SSH_USER@$SSH_HOST"
REMOTE_BACKEND="$REMOTE_ROOT/backend/python"
REMOTE_WEBPAGE="$REMOTE_ROOT/frontend/webpage"
REMOTE_DASHBOARD="$REMOTE_ROOT/frontend/dashboard"
SUDO="printf '%s\\n' $(umst_shell_quote "$SUDO_PASSWORD") | sudo -S -p ''"
export TARGET_SERVER SSH_KEY SSH_USER SSH_HOST REMOTE_ROOT NGINX_SITE NGINX_CONF REMOTE_URL DOMAIN CERT_NAME CERT_MODE SUDO_PASSWORD KEY REMOTE REMOTE_BACKEND REMOTE_WEBPAGE REMOTE_DASHBOARD SUDO BACKEND_SERVICE

if [ ! -f "$KEY" ]; then
    printf 'Missing SSH key at %s\n' "$KEY" >&2
    return 1 2>/dev/null || exit 1
fi
