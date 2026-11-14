#!/usr/bin/env bash
# Build (or with --check, compare) the whole-book reads of every stored book on
# the target, in its running backend container: book_read for the Web Demo
# (Theumst 0.0.15) and book_game_read for the game (0.0.16). Run it once right
# after deploying a release that adds or raises one, and after any change to
# book facts made outside ingestion, such as a restore. It is idempotent.
#   dev/sh/agent_build_book_reads.sh COM [--check] [--book ID ...]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_env

TARGET="$(upper "${1:-COM}")"
case "$TARGET" in
    COM|CN) ;;
    *) echo "Usage: $0 COM|CN [--check] [--book ID ...]" >&2; exit 2 ;;
esac
shift || true

# Pass on only the command's own options, checked here, so nothing else reaches the remote shell.
COMMAND_ARGS=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --check) COMMAND_ARGS="$COMMAND_ARGS --check" ;;
        --book)
            [ "$#" -ge 2 ] || { echo "--book needs a grimoire id" >&2; exit 2; }
            case "$2" in
                ''|*[!0-9]*) echo "--book needs a numeric grimoire id" >&2; exit 2 ;;
            esac
            COMMAND_ARGS="$COMMAND_ARGS --book $2"
            shift
            ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

remote_context "$TARGET"
# OpenSSH refuses keys with open permissions, so use a private copy and remove it
# on every exit. Nothing else in this script sets a trap, so this one stays.
SOURCE_KEY="$KEY"
RUNTIME_SSH_KEY_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t theumst_ssh)"
cleanup_runtime_key() {
    rm -rf -- "$RUNTIME_SSH_KEY_DIR"
}
trap cleanup_runtime_key EXIT
cp "$SOURCE_KEY" "$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
chmod 600 "$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
KEY="$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
SUDO="$(remote_sudo)"

ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" \
    "cd '$REMOTE_ROOT' && $SUDO docker compose --env-file .env -f compose.deploy.yml exec -T \
        backend python -m scripts.build_book_reads$COMMAND_ARGS"
