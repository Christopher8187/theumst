from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as Connection
from psycopg2.extras import RealDictCursor

from .config import get_settings


def connect() -> Connection:
    settings = get_settings()
    return psycopg2.connect(
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        cursor_factory=RealDictCursor,
    )


@contextmanager
def transaction() -> Iterator[tuple[Connection, RealDictCursor]]:
    con = connect()
    try:
        with con.cursor() as cur:
            yield con, cur
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _sql_files(sql_dir: Path) -> list[Path]:
    # The baseline schema must run before additive numbered migrations. The
    # repository historically names it schema.sql, which otherwise sorts last.
    files = sorted(
        (path for path in sql_dir.glob("*.sql") if path.is_file()),
        key=lambda path: (path.name != "schema.sql", path.name),
    )
    if not files:
        raise RuntimeError(f"No SQL schema files found in {sql_dir}")
    return files


def initialize_database(max_attempts: int = 30) -> None:
    """Apply the local-development schema replay.

    Production releases use the explicit checksummed 006/007 runner instead.
    Keeping the guard here prevents another caller from accidentally replaying
    historical fixture/seed migrations outside an explicitly local stack.
    """

    settings = get_settings()
    if settings.db_schema_startup_mode != "replay" or settings.server != "LOCAL":
        raise RuntimeError("Historical database replay is restricted to LOCAL")
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with transaction() as (_, cur):
                for path in _sql_files(settings.sql_dir):
                    cur.execute(path.read_text(encoding="utf-8"))
            return
        except psycopg2.OperationalError as exc:
            last_error = exc
            time.sleep(min(attempt, 5))
        except psycopg2.Error:
            raise
    raise RuntimeError(f"Database was not ready after {max_attempts} attempts: {last_error}")
