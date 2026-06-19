#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"

umst_find_npm || fail "Missing npm. Install Node.js LTS, then reopen your terminal."

printf 'Using npm: %s\n' "${UMST_NPM[*]}"
"${UMST_NPM[@]}" --version

if [ ! -f "$WEBPAGE_DIR/package.json" ]; then
    fail "Missing package.json at $WEBPAGE_DIR/package.json."
fi

cd "$WEBPAGE_DIR"
echo "Installing/updating Vue webpage packages..."
"${UMST_NPM[@]}" install --no-audit --no-fund

echo "Building Vue webpage..."
"${UMST_NPM[@]}" run build

echo "Vue webpage built successfully."
