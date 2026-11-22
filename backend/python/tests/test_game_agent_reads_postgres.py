"""Opt-in real PostgreSQL checks of 0.0.19: migration 018, the kinds 'search' and 'graph', and the game
agents' graph reads over a small book.

Set THEUMST_GAME_AGENT_DB_TESTS=1 with LOCAL loopback database settings and a PostgreSQL account that may
create a database. The fixtures build UUID-named databases from schema.sql and drop them afterwards; the
configured database is untouched. Migration 018 runs through the reviewed runner on a database as 0.0.18
left it. The routes are called through the application, so the key check, the counts, the visibility
filters and the graph queries are PostgreSQL's own. Nothing here reaches Qdrant or an embedding provider:
the search route is called only where it answers from PostgreSQL alone.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import RealDictCursor

from app import database, reviewed_migrations
from app.config import get_settings
from app.main import create_app
from app.security import hash_password, hash_secret
from app.services import game_search
from app.services.book_ingestion import _upsert_book, _upsert_objects, _upsert_sections

pytestmark = pytest.mark.skipif(
    os.getenv("THEUMST_GAME_AGENT_DB_TESTS") != "1", reason="Explicit isolated PostgreSQL acceptance only"
)

INDEXES = ("knowledge_active_crystal_idx", "knowledge_active_source_key_idx", "grimoire_hidden_idx")
CHECKS = ("api_rate_window_kind_check", "api_usage_daily_kind_check")
BACKUP = "0" * 64


@contextmanager
def disposable_database(prefix):
    """A UUID-named database made from schema.sql, which transaction() uses until it is dropped."""
    from psycopg2 import sql
    settings = get_settings()
    assert settings.server == "LOCAL" and settings.db_host in {"127.0.0.1", "localhost"}
    name = f"{prefix}_{uuid4().hex}"
    admin = database.connect()
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

    def connect():
        return psycopg2.connect(dbname=name, user=settings.db_user, password=settings.db_password,
                                host=settings.db_host, port=settings.db_port, cursor_factory=RealDictCursor)

    patch = pytest.MonkeyPatch()
    patch.setattr(database, "connect", connect)
    try:
        with database.transaction() as (_, cur):
            cur.execute((settings.sql_dir / "schema.sql").read_text(encoding="utf-8"))
        yield name
    finally:
        patch.undo()
        with admin.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


def catalogue() -> dict[str, str]:
    """The two kind checks' and the three indexes' definitions as PostgreSQL holds them."""
    with database.transaction() as (_, cur):
        cur.execute("SELECT conname AS name, pg_get_constraintdef(oid) AS definition FROM pg_constraint "
                    "WHERE conname = ANY(%s)", (list(CHECKS),))
        found = {row["name"]: row["definition"] for row in cur.fetchall()}
        cur.execute("SELECT indexrelid::regclass::text AS name, pg_get_indexdef(indexrelid) AS definition "
                    "FROM pg_index WHERE indexrelid::regclass::text = ANY(%s)", (list(INDEXES),))
        found.update({row["name"]: row["definition"] for row in cur.fetchall()})
    return found


def as_0_0_18_left_it() -> None:
    """Undo 018 on a fresh database: the two kinds only, none of the three indexes."""
    with database.transaction() as (_, cur):
        for index in INDEXES:
            cur.execute(f"DROP INDEX {index}")
        for table in ("api_rate_window", "api_usage_daily"):
            cur.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_kind_check")
            cur.execute(f"ALTER TABLE {table} ADD CONSTRAINT {table}_kind_check "
                        "CHECK (kind IN ('book', 'character'))")


def account(authority: str) -> dict:
    """A confirmed account of the given authority with one regular standard key."""
    name = f"{authority}_{uuid4().hex[:10]}"
    raw = f"umst_read_{uuid4().hex}"
    with database.transaction() as (_, cur):
        cur.execute(
            """INSERT INTO "user" (username, email, password_hash, authority_id, email_verified_at)
               SELECT %s, %s, %s, authority_id, now() FROM authority WHERE name = %s RETURNING user_id""",
            (name, f"{name}@example.invalid", hash_password("unused-passphrase"), authority),
        )
        user_id = cur.fetchone()["user_id"]
        cur.execute(
            """INSERT INTO api_key (user_id, api_rate_id, name, key_prefix, key_hash, key_type)
               VALUES (%s, 1, 'regular', %s, %s, 'regular') RETURNING api_key_id""",
            (user_id, raw[:16], hash_secret(raw)),
        )
        key_id = cur.fetchone()["api_key_id"]
    return {"user_id": user_id, "api_key_id": key_id, "headers": {"X-API-Key": raw}}


def counted(key: dict) -> tuple[dict, dict]:
    with database.transaction() as (_, cur):
        cur.execute("SELECT kind, request_count FROM api_rate_window WHERE api_key_id = %s", (key["api_key_id"],))
        window = {row["kind"]: row["request_count"] for row in cur.fetchall()}
        cur.execute("SELECT kind, sum(request_count)::int AS n FROM api_usage_daily WHERE api_key_id = %s "
                    "GROUP BY kind", (key["api_key_id"],))
        daily = {row["kind"]: row["n"] for row in cur.fetchall()}
    return window, daily


# --- migration 018 -------------------------------------------------------------------------------------

def test_018_applies_alone_on_a_database_as_0_0_18_left_it_and_runs_twice_more():
    with disposable_database("theumst_agent_reads_fresh"):
        reviewed_migrations.assert_database_schema_ready()
        fresh = catalogue()
    assert sorted(fresh) == sorted((*CHECKS, *INDEXES))
    assert "'search'::text" in fresh["api_rate_window_kind_check"] and "'graph'::text" in fresh[
        "api_usage_daily_kind_check"]

    with disposable_database("theumst_agent_reads_018"):
        as_0_0_18_left_it()
        key = account("betatester")
        with database.transaction() as (_, cur):
            # Rows 0.0.18 wrote stay as they are.
            cur.execute("INSERT INTO api_rate_window (api_key_id, kind, request_count) VALUES (%s, 'book', 3), "
                        "(%s, 'character', 2)", (key["api_key_id"], key["api_key_id"]))
            cur.execute("INSERT INTO api_usage_daily (api_key_id, day, kind, request_count) "
                        "VALUES (%s, current_date, 'book', 3)", (key["api_key_id"],))
        before = counted(key)
        with pytest.raises(reviewed_migrations.MigrationSafetyError, match="game_agent_reads_v1"):
            reviewed_migrations.assert_database_schema_ready()

        result = reviewed_migrations.apply_reviewed_migrations(backup_sha256=BACKUP)
        actions = {row["migration"]: row["action"] for row in result["migrations"]}
        assert actions.pop("game_agent_reads_v1") == "applied"
        assert set(actions.values()) == {"already_applied"}
        reviewed_migrations.assert_database_schema_ready()
        assert catalogue() == fresh
        assert counted(key) == before

        sql_text = (get_settings().sql_dir / "018_game_agent_reads.sql").read_text(encoding="utf-8")
        for _ in range(2):
            with database.transaction() as (_, cur):
                cur.execute(sql_text)
        assert catalogue() == fresh
        again = reviewed_migrations.apply_reviewed_migrations(backup_sha256=BACKUP)
        assert {row["action"] for row in again["migrations"]} == {"already_applied"}

        with database.transaction() as (_, cur):
            cur.execute("INSERT INTO api_rate_window (api_key_id, kind) VALUES (%s, 'search'), (%s, 'graph')",
                        (key["api_key_id"], key["api_key_id"]))
        with pytest.raises(psycopg2.errors.CheckViolation):
            with database.transaction() as (_, cur):
                cur.execute("INSERT INTO api_usage_daily (api_key_id, day, kind) VALUES (%s, current_date, 'other')",
                            (key["api_key_id"],))


# --- the routes against PostgreSQL ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def application():
    with disposable_database("theumst_agent_reads_routes"):
        yield create_app(initialize_services=False)


@pytest.fixture
def client(application):
    return TestClient(application)


def book(title: str, *, demo: bool, objects: list[dict]) -> dict[str, int]:
    """A book of two sections with the given objects, and its dependency arrows; ids by source key."""
    with database.transaction() as (_, cur):
        grimoire_id, language_id = _upsert_book(
            cur, {"source_key": f"book-{uuid4().hex[:8]}", "title": title, "metadata": {"demo": demo}},
        )
        sections = _upsert_sections(cur, grimoire_id, language_id, [
            {"source_key": "one", "section_number": "1", "section_name": "Groups"},
            {"source_key": "two", "section_number": "2", "section_name": "Rings"},
        ])
        made = _upsert_objects(cur, grimoire_id=grimoire_id, language_id=language_id, sections=sections,
                               objects=[{key: value for key, value in obj.items() if key != "uses"}
                                        for obj in objects])
        ids = {key: int(row["knowledge_id"]) for key, row in made.items()}
        for key, knowledge_id in ids.items():
            cur.execute("INSERT INTO knowledge_graph_node (grimoire_id, knowledge_id, stable_knowledge_id, graph_role) "
                        "VALUES (%s, %s, %s, 'backbone')", (grimoire_id, knowledge_id, key))
        for obj in objects:
            for used in obj.get("uses", ()):
                # In `dependency` the target uses the source.
                cur.execute("INSERT INTO knowledge_graph_edge (grimoire_id, source_knowledge_id, target_knowledge_id, "
                            "relation_type) VALUES (%s, %s, %s, 'dependency')",
                            (grimoire_id, ids[used], ids[obj["source_key"]]))
    return {"grimoire_id": grimoire_id, **ids}


def test_the_graph_reads_answer_from_postgresql_and_count_as_graph(client):
    crystal = f"crystal-{uuid4().hex[:8]}"
    shown = book("Algebra", demo=True, objects=[
        {"source_key": "def", "section_source_key": "one", "type": "definition", "name": "Group",
         "statement": "A group is a set with an associative operation."},
        {"source_key": "lem", "section_source_key": "one", "type": "lemma", "name": "Identity is unique",
         "statement": "A group has one identity.", "uses": ["def"], "crystal_source_key": crystal},
        {"source_key": "thm", "section_source_key": "two", "type": "theorem", "name": "Inverses are unique",
         "statement": "Each element has one inverse.", "uses": ["lem", "def"]},
    ])
    hidden = book("Hidden", demo=False, objects=[
        {"source_key": "lem", "section_source_key": "one", "type": "lemma", "name": "Identity is unique",
         "statement": "A group has one identity.", "crystal_source_key": crystal},
    ])
    reader = account("betatester")
    headers = reader["headers"]

    answer = client.get("/api/game/graph/object", params={"knowledge_id": shown["thm"]}, headers=headers)
    assert answer.status_code == 200, answer.text
    assert answer.headers["cache-control"] == "no-store"
    body = answer.json()
    assert body["object"]["knowledge_id"] == shown["thm"] and body["object"]["grimoire_id"] == shown["grimoire_id"]
    assert {row["knowledge_id"] for row in body["dependencies"]} == {shown["lem"], shown["def"]}

    uses = client.get("/api/game/graph/uses", params={"knowledge_id": shown["thm"]}, headers=headers).json()
    used_by = client.get("/api/game/graph/used-by", params={"knowledge_id": shown["lem"]}, headers=headers).json()
    assert {row["knowledge_id"] for row in uses["results"]} == {shown["lem"], shown["def"]}
    assert [row["knowledge_id"] for row in used_by["results"]] == [shown["thm"]]

    # The hidden book's member of the shared crystal is neither counted nor listed.
    members = client.get("/api/game/graph/crystal", params={"knowledge_id": shown["lem"]}, headers=headers).json()
    assert members["crystal_size"] == 1 and [row["knowledge_id"] for row in members["members"]] == [shown["lem"]]
    assert client.get("/api/game/graph/object", params={"knowledge_id": hidden["lem"]},
                      headers=headers).json()["code"] == "not_found"

    closure = client.get("/api/game/graph/closure", params={"knowledge_id": shown["thm"], "direction": "down"},
                         headers=headers)
    assert closure.status_code == 200, closure.text
    assert closure.json()["crystals"][0]["depth"] == 0
    section = client.get("/api/game/graph/section", params={"knowledge_id": shown["def"]}, headers=headers).json()
    assert [row["knowledge_id"] for row in section["objects"]] == [shown["def"], shown["lem"]]
    around = client.get("/api/game/graph/around", params={"knowledge_id": shown["lem"]}, headers=headers).json()
    assert [row["knowledge_id"] for row in around["before"]] == [shown["def"]]
    assert [row["knowledge_id"] for row in around["after"]] == [shown["thm"]]
    assert client.get("/api/game/graph/pages", params={"knowledge_id": shown["def"]},
                      headers=headers).json()["pages"] == []
    match = client.post("/api/game/graph/match", headers=headers,
                        json={"objects": [{"source_key": "thm", "grimoire_id": shown["grimoire_id"]},
                                          {"source_key": "nothing"}]}).json()
    assert [row["knowledge_id"] for row in match["objects"]] == [shown["thm"], None]

    # Ten graph calls above, the 404 among them; the search's neighbours of an object of no shown book
    # answer 404 from PostgreSQL alone and count once as 'search'.
    missing = client.get("/api/game/search/neighbours", params={"knowledge_id": hidden["lem"]}, headers=headers)
    assert missing.status_code == 404 and missing.json()["code"] == "not_found"
    assert counted(reader) == ({"graph": 10, "search": 1}, {"graph": 10, "search": 1})


def test_an_account_without_web_demo_access_reads_nothing_and_counts_nothing(client):
    shown = book("Algebra", demo=True, objects=[
        {"source_key": "def", "section_source_key": "one", "type": "definition", "statement": "A group is"},
    ])
    outsider = account("user")
    for path in ("/api/game/graph/object", "/api/game/search/neighbours"):
        answer = client.get(path, params={"knowledge_id": shown["def"]}, headers=outsider["headers"])
        assert answer.status_code == 403 and answer.json()["code"] == "demo_access_required"
    assert counted(outsider) == ({}, {})


def test_the_three_indexes_serve_the_agents_queries(application):
    # A book this small is read faster without an index, so the planner is told not to scan tables; what is
    # checked is that each query's WHERE lets the partial index serve it.
    def plan(cur, sql, params):
        cur.execute("EXPLAIN " + sql, params)
        return " ".join(row["QUERY PLAN"] for row in cur.fetchall())

    sent = []

    class Recording:
        """book_scope's cursor: records what it sends, then sends it."""

        def __init__(self, cur):
            self.cur = cur

        def execute(self, sql, params=None):
            sent.append((sql, params))
            self.cur.execute(sql, params)

        def fetchall(self):
            return self.cur.fetchall()

    with database.transaction() as (_, cur):
        cur.execute("SET LOCAL enable_seqscan = off")
        assert "knowledge_active_crystal_idx" in plan(cur, game_search._CRYSTAL_SIZE_SQL, ([1, 2],))
        assert "knowledge_active_source_key_idx" in plan(cur, game_search._SOURCE_BY_KEY_SQL, ("key-1",))
        game_search.book_scope(Recording(cur))
        hidden_sql, hidden_params = sent[0]
        assert "IS DISTINCT FROM 'true'" in hidden_sql
        assert "grimoire_hidden_idx" in plan(cur, hidden_sql, hidden_params)
