#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

"$SCRIPT_DIR/build_webpage_local.sh"
"$SCRIPT_DIR/build_dashboard_local.sh"
