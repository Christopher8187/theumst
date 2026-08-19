#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_env

TARGET="$(upper "${1:-COM}")"
BOOK_SOURCE_KEY="${2:-}"
case "$TARGET" in
    COM|CN) ;;
    *) echo "Usage: $0 COM|CN BOOK_SOURCE_KEY" >&2; exit 2 ;;
esac
if [[ ! "$BOOK_SOURCE_KEY" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
    echo "BOOK_SOURCE_KEY must contain only letters, digits, dot, underscore, colon, or hyphen." >&2
    exit 2
fi

remote_context "$TARGET"
SOURCE_KEY="$KEY"
RUNTIME_SSH_KEY_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t theumst_verify)"
cleanup_runtime_key() {
    rm -rf -- "$RUNTIME_SSH_KEY_DIR"
}
trap cleanup_runtime_key EXIT
cp "$SOURCE_KEY" "$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
chmod 600 "$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
KEY="$RUNTIME_SSH_KEY_DIR/$(basename "$SOURCE_KEY")"
SUDO="$(remote_sudo)"

SQL="SELECT g.grimoire_id,
    (SELECT count(*) FROM section s WHERE s.grimoire_id=g.grimoire_id),
    (SELECT count(*) FROM knowledge k JOIN section s ON s.section_id=k.section_id
        WHERE s.grimoire_id=g.grimoire_id AND k.is_active),
    (SELECT count(*) FROM semantic_projection sp
        JOIN knowledge k ON k.knowledge_id=sp.knowledge_id
        JOIN section s ON s.section_id=k.section_id
        WHERE s.grimoire_id=g.grimoire_id AND sp.is_active),
    (SELECT count(*) FROM embedding e
        JOIN semantic_projection sp ON sp.semantic_projection_id=e.semantic_projection_id
        JOIN knowledge k ON k.knowledge_id=sp.knowledge_id
        JOIN section s ON s.section_id=k.section_id
        WHERE s.grimoire_id=g.grimoire_id
          AND e.status='indexed' AND e.deleted_at IS NULL),
    (SELECT count(*) FROM book_image bi
        WHERE bi.grimoire_id=g.grimoire_id AND bi.is_active),
    (SELECT min(url) FROM book_image bi
        WHERE bi.grimoire_id=g.grimoire_id AND bi.is_active)
FROM grimoire g WHERE g.source_key='${BOOK_SOURCE_KEY}';"
printf -v SQL_QUOTED '%q' "$SQL"

PYTHON_CHECK="import httpx; from app.config import get_settings; s=get_settings(); r=httpx.get(s.qdrant_url+'/collections/'+s.qdrant_collection, headers={'api-key': s.qdrant_api_key}, timeout=30); r.raise_for_status(); x=r.json()['result']; print('collection={}|points={}|indexed={}|status={}'.format(s.qdrant_collection, x.get('points_count'), x.get('indexed_vectors_count'), x.get('status')))"
printf -v PYTHON_CHECK_QUOTED '%q' "$PYTHON_CHECK"

ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" \
    "cd '$REMOTE_ROOT' && \
     $SUDO docker compose --env-file .env -f compose.deploy.yml exec -T db \
       psql -U postgres -d theumst -At -F '|' -c $SQL_QUOTED && \
     $SUDO docker compose --env-file .env -f compose.deploy.yml exec -T backend \
       python -c $PYTHON_CHECK_QUOTED"
