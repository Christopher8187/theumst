#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
. "$SCRIPT_DIR/_common.sh"
load_env

TARGET="${1:-local}"
SQL_FILE="$(mktemp)"
trap 'rm -f "$SQL_FILE"' EXIT
cat > "$SQL_FILE" <<'SQL'
DO $promote$
DECLARE
    matching_accounts integer;
BEGIN
    SELECT count(*) INTO matching_accounts
    FROM "user"
    WHERE lower(username) = 'christopher';

    IF matching_accounts = 0 THEN
        RAISE EXCEPTION 'No account with username christopher exists';
    ELSIF matching_accounts > 1 THEN
        RAISE EXCEPTION 'More than one case-insensitive christopher account exists';
    END IF;

    UPDATE "user"
    SET username = 'christopher',
        authority_id = (SELECT authority_id FROM authority WHERE name = 'superadmin')
    WHERE lower(username) = 'christopher';
END
$promote$;

SELECT u.user_id, u.username, u.email, a.name AS authority
FROM "user" u
JOIN authority a ON a.authority_id = u.authority_id
WHERE u.username = 'christopher';
SQL

promote_compose() {
    local compose_file="$1"
    echo "Promoting christopher using $compose_file ..."
    docker compose -f "$compose_file" exec -T db \
        psql -v ON_ERROR_STOP=1 -U "${DB_USER:-postgres}" -d "${DB_NAME:-theumst}" \
        < "$SQL_FILE"
}

promote_remote() {
    local remote_target="$1"
    TARGET="$remote_target"
    remote_context
    if [ -z "${REMOTE_ROOT:-}" ]; then
        echo "Missing REMOTE_ROOT_${remote_target}; cannot promote remotely." >&2
        return 1
    fi

    echo "Promoting christopher on $remote_target ($REMOTE) ..."
    remote_sql="/tmp/theumst_promote_christopher_$$.sql"
    scp "${SSH_OPTIONS[@]}" -i "$KEY" "$SQL_FILE" "$REMOTE:$remote_sql"

    if [ -n "${SUDO_PASSWORD:-}" ]; then
        prime="printf '%s\\n' '$SUDO_PASSWORD' | sudo -S -p '' true && sudo"
    else
        prime="sudo"
    fi

    ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" \
        "cd '$REMOTE_ROOT' && $prime docker compose --env-file .env -f compose.deploy.yml exec -T db psql -v ON_ERROR_STOP=1 -U '${DB_USER:-postgres}' -d '${DB_NAME:-theumst}' < '$remote_sql'; status=\$?; rm -f '$remote_sql'; exit \$status"
}

case "${TARGET,,}" in
    local)
        promote_compose "$LOCAL_COMPOSE"
        ;;
    deploy)
        promote_compose "$DEPLOY_COMPOSE"
        ;;
    com)
        promote_remote COM
        ;;
    cn)
        promote_remote CN
        ;;
    all)
        promote_compose "$LOCAL_COMPOSE"
        promote_remote COM
        promote_remote CN
        ;;
    *)
        echo "Usage: $0 [local|deploy|COM|CN|all]" >&2
        exit 2
        ;;
esac
