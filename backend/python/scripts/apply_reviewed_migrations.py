from __future__ import annotations

import argparse
import json

from app.reviewed_migrations import MigrationSafetyError, apply_reviewed_migrations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply checksum-pinned database migration 006 after a verified backup."
    )
    parser.add_argument("--backup-sha256", required=True)
    arguments = parser.parse_args()
    try:
        result = apply_reviewed_migrations(backup_sha256=arguments.backup_sha256)
    except MigrationSafetyError as exc:
        parser.error(str(exc))
    except Exception:
        # Database exception detail may contain operational identifiers. The
        # transaction context rolls back; detailed review remains in protected
        # database logs rather than ordinary release output.
        parser.error("Reviewed migration failed; the transaction was rolled back")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
