#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_env
show_env

if [ "${BASH_SOURCE[0]}" != "$0" ]; then
    return 0
fi
pause_if_clicked
