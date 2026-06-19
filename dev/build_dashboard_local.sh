#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"

umst_find_npm || fail "Missing npm. Install Node.js LTS, then reopen your terminal."

printf 'Using npm: %s\n' "${UMST_NPM[*]}"
"${UMST_NPM[@]}" --version

if [ ! -f "$DASHBOARD_DIR/package.json" ]; then
    fail "Missing package.json at $DASHBOARD_DIR/package.json."
fi

cd "$DASHBOARD_DIR"
echo "Installing/updating Vue packages..."
"${UMST_NPM[@]}" install --no-audit --no-fund

echo "Building Vue dashboard..."
"${UMST_NPM[@]}" run build

echo "Vue dashboard built successfully."
