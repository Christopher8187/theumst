#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LOCAL_ONLY=1 . "$SCRIPT_DIR/load_env.sh"

umst_find_npm || fail "Missing npm. Install Node.js LTS, then reopen your terminal."

printf 'Using npm: %s\n' "${UMST_NPM[*]}"
"${UMST_NPM[@]}" --version

build_vue_app() {
    local app_name="$1"
    local app_dir="$2"

    if [ ! -f "$app_dir/package.json" ]; then
        fail "Missing package.json at $app_dir/package.json."
    fi

    cd "$app_dir"
    echo "Installing/updating Vue packages for $app_name..."
    "${UMST_NPM[@]}" install --no-audit --no-fund

    echo "Building Vue $app_name..."
    "${UMST_NPM[@]}" run build
}

build_vue_app "webpage" "$WEBPAGE_DIR"
build_vue_app "dashboard" "$DASHBOARD_DIR"

echo "Vue apps built successfully."
