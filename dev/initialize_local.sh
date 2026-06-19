#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"
trap 'say "Local initialization failed."' ERR

say "Initializing local backend and Vue apps."

echo
echo "=== Python backend ==="
cd "$ROOT/backend/python"

if ! umst_backend_python >/dev/null 2>&1; then
    umst_system_python -m venv .venv || fail "Could not create Python venv. Install python3-venv if needed."
fi
BACKEND_PYTHON="$(umst_backend_python)" || fail "Missing backend venv Python."

"$BACKEND_PYTHON" -m pip install --upgrade pip
"$BACKEND_PYTHON" -m pip install -r requirements.txt

echo
echo "=== PostgreSQL ==="
export PGPASSWORD="$DB_PASSWORD"
if ! command -v psql >/dev/null 2>&1; then
    fail "Missing psql. On Ubuntu: sudo apt install postgresql-client"
fi
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
fi
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/backend/sql/schema.sql"

echo
echo "=== Vue apps ==="
"$SCRIPT_DIR/build_dashboard_local.sh"

say "Local backend and Vue apps initialized."
umst_pause_if_requested
