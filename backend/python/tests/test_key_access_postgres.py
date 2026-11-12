"""Opt-in real PostgreSQL checks of 0.0.13: book reads need the Web Demo's access,
one key cannot open a character on two installs, and migration 015.

Set THEUMST_KEY_ACCESS_DB_TESTS=1 with LOCAL loopback database settings and a
PostgreSQL account that may create a database. The fixtures build UUID-named
databases from schema.sql and drop them afterwards; the configured database is
untouched. Requests go through the application, so the key and session queries,
the authority's access points, the leases, now() and the transactions are
PostgreSQL's own. Book images go to a temporary LOCAL storage folder.
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
from app.services import storage
from app.services.book_ingestion import _upsert_book, _upsert_objects, _upsert_sections


pytestmark = pytest.mark.skipif(
    os.getenv("THEUMST_KEY_ACCESS_DB_TESTS") != "1", reason="Explicit isolated PostgreSQL acceptance only"
)

HERE, THERE = "k7m2qx", "p4n8wz"  # two installs of the game
IMAGE_KEY = "books/{grimoire_id}/images/figure-1.png"
IMAGE_BYTES = b"\x89PNG figure"


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


@pytest.fixture(scope="module")
def application():
    with disposable_database("theumst_key_access_test"):
        yield create_app(initialize_services=False)


@pytest.fixture(autouse=True)
def fresh_rows(application, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "local_root", lambda: tmp_path.resolve())
    with database.transaction() as (_, cur):
        cur.execute('TRUNCATE "user", grimoire, knowledge_crystal CASCADE')


@pytest.fixture
def client(application):
    return TestClient(application)


def sql_one(query, params=()):
    with database.transaction() as (_, cur):
        cur.execute(query, params)
        return cur.fetchone()


def account(authority):
    """A confirmed account of the given authority with a regular key, a master key if asked, and a session."""
    name = f"{authority}_{uuid4().hex[:10]}"
    with database.transaction() as (_, cur):
        cur.execute(
            """INSERT INTO "user" (username, email, password_hash, authority_id, email_verified_at)
               SELECT %s, %s, %s, authority_id, now() FROM authority WHERE name = %s RETURNING user_id""",
            (name, f"{name}@example.invalid", hash_password("unused-passphrase"), authority),
        )
        user_id = cur.fetchone()["user_id"]
        keys = {}
        for key_type in ("regular", "master"):
            raw = f"umst_{key_type[:4]}_{uuid4().hex}"
            cur.execute(
                """INSERT INTO api_key (user_id, api_rate_id, name, key_prefix, key_hash, key_type)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING api_key_id""",
                (user_id, 1 if key_type == "regular" else None, key_type, raw[:16], hash_secret(raw), key_type),
            )
            keys[key_type] = {"raw": raw, "api_key_id": cur.fetchone()["api_key_id"]}
        token = uuid4().hex + uuid4().hex
        cur.execute(
            "INSERT INTO web_session (user_id, token_hash, expires_at) VALUES (%s, %s, now() + interval '1 day')",
            (user_id, hash_secret(token)),
        )
    cookie = {"Cookie": f"{get_settings().cookie_name}={token}"}
    return {"user_id": user_id, "key": keys["regular"], "master": keys["master"], "cookie": cookie}


def key_header(key):
    return {"X-API-Key": key["raw"]}


def demo_book():
    """A Web Demo book of one object with one figure, its bytes in LOCAL storage."""
    with database.transaction() as (_, cur):
        grimoire_id, language_id = _upsert_book(
            cur, {"source_key": f"book-{uuid4().hex[:8]}", "title": "Algebra", "metadata": {"demo": True}},
        )
        sections = _upsert_sections(cur, grimoire_id, language_id, [
            {"source_key": "one", "section_number": "1", "section_name": "Groups"},
        ])
        objects = _upsert_objects(cur, grimoire_id=grimoire_id, language_id=language_id, sections=sections, objects=[
            {"source_key": "definition-1", "section_source_key": "one", "type": "definition", "statement": "A group is"},
        ])
        knowledge_id = objects["definition-1"]["knowledge_id"]
        image_key = IMAGE_KEY.format(grimoire_id=grimoire_id)
        cur.execute(
            """INSERT INTO book_image (grimoire_id, knowledge_id, source_image_id, storage_key, url)
               VALUES (%s, %s, 'figure-1', %s, %s) RETURNING book_image_id""",
            (grimoire_id, knowledge_id, image_key, f"http://localhost/api/v1/storage/{image_key}"),
        )
        cur.execute(
            "INSERT INTO book_image_knowledge (book_image_id, knowledge_id, link_type) VALUES (%s, %s, 'figure')",
            (cur.fetchone()["book_image_id"], knowledge_id),
        )
    storage.write_bytes(image_key, IMAGE_BYTES)
    return {"grimoire_id": grimoire_id, "knowledge_id": knowledge_id, "image": f"/api/v1/storage/{image_key}"}


def book_reads(book):
    return [f"/api/v1/knowledge?grimoire_id={book['grimoire_id']}", f"/api/v1/knowledge/{book['knowledge_id']}", book["image"]]


def counted(key):
    """The key's recorded requests as {kind: count}, per minute window and per day."""
    with database.transaction() as (_, cur):
        cur.execute("SELECT kind, request_count FROM api_rate_window WHERE api_key_id = %s", (key["api_key_id"],))
        window = {row["kind"]: row["request_count"] for row in cur.fetchall()}
        cur.execute("SELECT kind, sum(request_count)::int AS n FROM api_usage_daily WHERE api_key_id = %s GROUP BY kind",
                    (key["api_key_id"],))
        daily = {row["kind"]: row["n"] for row in cur.fetchall()}
    return window, daily


def assert_demo_access_required(response):
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "demo_access_required"


# --- book reads --------------------------------------------------------------------------

def test_an_ordinary_accounts_key_reads_no_book_and_counts_nothing(client):
    reader, book = account("user"), demo_book()
    for path in book_reads(book):
        assert_demo_access_required(client.get(path, headers=key_header(reader["key"])))
    assert counted(reader["key"]) == ({}, {})


@pytest.mark.parametrize("authority", ["betatester", "manager", "admin", "superadmin"])
def test_a_key_of_an_account_the_web_demo_admits_reads_books(client, authority):
    reader, book = account(authority), demo_book()
    listed = client.get(book_reads(book)[0], headers=key_header(reader["key"]))
    assert listed.status_code == 200, listed.text
    assert [item["knowledge_id"] for item in listed.json()["items"]] == [book["knowledge_id"]]
    one = client.get(book_reads(book)[1], headers=key_header(reader["key"])).json()["item"]
    assert one["images"][0]["url"] == book["image"]
    image = client.get(one["images"][0]["url"], headers=key_header(reader["key"]))
    assert image.status_code == 200 and image.content == IMAGE_BYTES
    assert counted(reader["key"]) == ({"book": 3}, {"book": 3})


def test_a_master_key_keeps_its_book_access_whatever_its_account(client):
    # A master key of an ordinary account, as only an admin's upgrade could make one.
    publisher, book = account("user"), demo_book()
    for path in book_reads(book):
        assert client.get(path, headers=key_header(publisher["master"])).status_code == 200
    assert counted(publisher["master"]) == ({}, {"book": 3})


def test_approving_an_accounts_web_demo_request_opens_book_reads_to_its_keys(client):
    reader, reviewer, book = account("user"), account("admin"), demo_book()
    assert_demo_access_required(client.get(book_reads(book)[1], headers=key_header(reader["key"])))
    asked = client.post("/api/demo/access/request", json={"message": "Algebra please"}, headers=reader["cookie"])
    assert asked.status_code == 200, asked.text
    approved = client.post(f"/api/demo/access/requests/{reader['user_id']}/approve", json={"note": ""},
                           headers=reviewer["cookie"])
    assert approved.status_code == 200, approved.text
    assert client.get("/api/demo/auth-check", headers=reader["cookie"]).status_code == 204
    for path in book_reads(book):
        assert client.get(path, headers=key_header(reader["key"])).status_code == 200


def test_book_images_follow_the_web_demos_own_check_for_a_session(client):
    reader, tester, book = account("user"), account("betatester"), demo_book()
    # The proxy's check and the image read agree for each session.
    assert client.get("/api/demo/auth-check", headers=reader["cookie"]).status_code == 403
    assert_demo_access_required(client.get(book["image"], headers=reader["cookie"]))
    assert client.get("/api/demo/auth-check", headers=tester["cookie"]).status_code == 204
    image = client.get(book["image"], headers=tester["cookie"])
    assert image.status_code == 200 and image.content == IMAGE_BYTES
    assert image.headers["cache-control"] == "private, no-store"
    unsigned = client.get(book["image"])
    assert unsigned.status_code == 401 and unsigned.content != IMAGE_BYTES
    # A session counts against no key.
    assert counted(tester["key"]) == ({}, {})


def test_the_game_stays_open_to_an_account_outside_the_web_demo(client):
    player = account("user")
    headers = {**key_header(player["key"]), "X-Install-Id": HERE}
    assert client.get("/api/game/me", headers=headers).json()["user_id"] == player["user_id"]
    made = client.post("/api/game/characters", json={"name": "Aria", "sex": "female", "save": {"day": 1}, "save_version": 1},
                       headers=headers)
    assert made.status_code == 201, made.text
    assert client.post(f"/api/game/characters/{made.json()['character']['character_id']}/open", headers=headers).status_code == 200
    assert counted(player["key"]) == ({"character": 3}, {"character": 3})


# --- one key on two installs ---------------------------------------------------------------

def make_character(client, key):
    response = client.post("/api/game/characters", headers=key_header(key),
                           json={"name": "Aria", "sex": "female", "save": {"day": 1}, "save_version": 1})
    assert response.status_code == 201, response.text
    return response.json()["character"]["character_id"]


def lease(character_id):
    return sql_one(
        """SELECT lease_api_key_id, lease_install_id, lease_expires_at > now() AS live
           FROM "character" WHERE character_id = %s""",
        (character_id,),
    )


def test_one_key_cannot_open_a_character_on_two_installs(client):
    player = account("user")
    character_id = make_character(client, player["key"])
    here = {**key_header(player["key"]), "X-Install-Id": HERE}
    there = {**key_header(player["key"]), "X-Install-Id": THERE}
    base = f"/api/game/characters/{character_id}"

    opened = client.post(f"{base}/open", headers=here)
    assert opened.status_code == 200, opened.text
    revision = opened.json()["revision"]
    assert lease(character_id) == {"lease_api_key_id": player["key"]["api_key_id"], "lease_install_id": HERE, "live": True}

    for method, path, body in (("POST", "open", None), ("POST", "heartbeat", None),
                               ("PUT", "data", {"save": {"day": 9}, "save_version": 1, "revision": revision}),
                               ("DELETE", "", {"name": "Aria"})):
        refused = client.request(method, f"{base}/{path}".rstrip("/"), json=body, headers=there)
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "open_elsewhere" and 0 < refused.json()["seconds_left"] <= 120
    listed = client.get("/api/game/characters", headers=there).json()["characters"]
    assert listed[0]["open_elsewhere"] is True
    assert client.post(f"{base}/close", headers=there).json() == {"released": False}

    saved = client.put(f"{base}/data", json={"save": {"day": 2}, "save_version": 1, "revision": revision}, headers=here)
    assert saved.status_code == 200, saved.text
    assert lease(character_id)["lease_install_id"] == HERE
    assert client.post(f"{base}/close", headers=here).json() == {"released": True}
    assert lease(character_id) == {"lease_api_key_id": None, "lease_install_id": None, "live": None}

    assert client.post(f"{base}/open", headers=there).status_code == 200
    assert lease(character_id)["lease_install_id"] == THERE


def test_a_lapsed_lease_goes_to_the_other_install_and_the_first_is_then_refused(client):
    player = account("user")
    character_id = make_character(client, player["key"])
    here = {**key_header(player["key"]), "X-Install-Id": HERE}
    there = {**key_header(player["key"]), "X-Install-Id": THERE}
    base = f"/api/game/characters/{character_id}"
    assert client.post(f"{base}/open", headers=here).status_code == 200
    with database.transaction() as (_, cur):  # the first computer slept past its lease
        cur.execute("""UPDATE "character" SET lease_expires_at = now() - interval '1 second' WHERE character_id = %s""",
                    (character_id,))
    # Not the sleeper's to renew from another install, but free to open.
    assert client.post(f"{base}/heartbeat", headers=there).json()["code"] == "not_open"
    assert client.post(f"{base}/open", headers=there).status_code == 200
    woke = client.post(f"{base}/heartbeat", headers=here)
    assert woke.status_code == 409 and woke.json()["code"] == "open_elsewhere"


def test_without_the_header_the_key_alone_decides_as_before(client):
    player = account("user")
    character_id = make_character(client, player["key"])
    base = f"/api/game/characters/{character_id}"
    assert client.post(f"{base}/open", headers={**key_header(player["key"]), "X-Install-Id": HERE}).status_code == 200
    # The game in players' hands sends no install id; its key's lease is its own.
    plain = key_header(player["key"])
    assert client.post(f"{base}/open", headers=plain).status_code == 200
    assert client.post(f"{base}/heartbeat", headers=plain).status_code == 200
    assert lease(character_id)["lease_install_id"] == HERE
    assert client.post(f"{base}/close", headers=plain).json() == {"released": True}
    assert lease(character_id)["lease_api_key_id"] is None


def test_a_malformed_install_id_is_refused_and_counts_nothing(client):
    player = account("user")
    for value in ("", "two words", "x" * 65):
        refused = client.get("/api/game/characters", headers={**key_header(player["key"]), "X-Install-Id": value})
        assert refused.status_code == 422 and refused.json()["errors"][0]["field"] == "X-Install-Id"
    assert counted(player["key"]) == ({}, {})


def test_the_column_refuses_an_install_id_the_api_would_refuse(client):
    player = account("user")
    character_id = make_character(client, player["key"])
    with pytest.raises(psycopg2.Error) as refused:
        with database.transaction() as (_, cur):
            cur.execute("""UPDATE "character" SET lease_install_id = 'two words' WHERE character_id = %s""",
                        (character_id,))
    assert refused.value.pgcode == "23514"
    assert refused.value.diag.constraint_name == "character_lease_install_id_check"


# --- migration 015 -------------------------------------------------------------------------------

def catalogue(cur):
    cur.execute(
        """SELECT data_type, is_nullable, column_default FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'character' AND column_name = 'lease_install_id'"""
    )
    column = cur.fetchone()
    cur.execute(
        """SELECT conname, pg_get_constraintdef(oid) AS definition FROM pg_constraint
           WHERE conrelid = '"character"'::regclass AND conname LIKE 'character_lease_install%'"""
    )
    return column, cur.fetchall()


def test_migration_015_brings_a_0_0_12_table_to_the_fresh_schema_and_can_run_again():
    with disposable_database("theumst_migration_015_test"):
        with database.transaction() as (_, cur):
            fresh = catalogue(cur)
            # The table as 0.0.12 left it, holding a character with a live lease.
            cur.execute('ALTER TABLE "character" DROP COLUMN lease_install_id')
            cur.execute(
                """INSERT INTO "user" (username, email, password_hash, authority_id, email_verified_at)
                   VALUES ('player', 'player@example.invalid', 'unused', 1, now()) RETURNING user_id"""
            )
            user_id = cur.fetchone()["user_id"]
            cur.execute("INSERT INTO character_data (data, save_version) VALUES ('{}'::jsonb, 1) RETURNING character_data_id")
            cur.execute(
                """INSERT INTO "character" (user_id, character_data_id, name, sex, lease_expires_at)
                   VALUES (%s, %s, 'Aria', 'female', now() + interval '1 minute')""",
                (user_id, cur.fetchone()["character_data_id"]),
            )
        with pytest.raises(reviewed_migrations.MigrationSafetyError, match="character_lease_install_v1"):
            reviewed_migrations.assert_database_schema_ready()

        first = reviewed_migrations.apply_reviewed_migrations(backup_sha256="0" * 64)
        actions = {entry["migration"]: entry["action"] for entry in first["migrations"]}
        assert actions.pop("character_lease_install_v1") == "applied"
        assert set(actions.values()) == {"already_applied"}
        reviewed_migrations.assert_database_schema_ready()
        with database.transaction() as (_, cur):
            assert catalogue(cur) == fresh
            cur.execute('SELECT count(*) AS leases, count(lease_install_id) AS installs FROM "character"')
            assert cur.fetchone() == {"leases": 1, "installs": 0}
            # Every statement can run again, as the runner never would.
            source = next(path for migration, path in reviewed_migrations.validated_migration_sources()
                          if migration.key == "character_lease_install_v1")
            cur.execute(source.read_text(encoding="utf-8"))
            cur.execute(source.read_text(encoding="utf-8"))
            assert catalogue(cur) == fresh

        again = reviewed_migrations.apply_reviewed_migrations(backup_sha256="0" * 64)
        assert {entry["action"] for entry in again["migrations"]} == {"already_applied"}
    assert fresh[0] == {"data_type": "text", "is_nullable": "YES", "column_default": None}
    assert fresh[1] == [{"conname": "character_lease_install_id_check",
                         "definition": "CHECK ((lease_install_id ~ '^[A-Za-z0-9_-]{1,64}$'::text))"}]
