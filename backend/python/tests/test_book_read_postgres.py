"""Opt-in real PostgreSQL checks of the whole-book reads, from ingestion to the routes: the Web
Demo's (0.0.15) and the game's, with the game's notes (0.0.16).

Set THEUMST_BOOK_READ_DB_TESTS=1 with LOCAL loopback database settings and a PostgreSQL account
that may create a database. The fixtures build UUID-named databases from schema.sql and drop them
afterwards; the configured database is untouched. Books arrive through the master-key Whole-book
upload and single-object submission, and are read through the Web Demo's routes with a session and
through /api/game with a regular key, so the queries, the advisory lock, the savepoints and the
transactions are PostgreSQL's own. No book has embeddings, so nothing reaches Qdrant. Image rows
are written through ingestion's own _finalize_images; the one image read through /api/v1/storage
has its bytes from a stand-in for storage.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import threading
import zipfile
from contextlib import contextmanager
from datetime import timezone
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import RealDictCursor

from app import database, reviewed_migrations
from app.config import get_settings
from app.main import create_app
from app.security import hash_password, hash_secret
from app.services import book_ingestion, book_read, storage
from app.services.api_keys import create_regular_key
from app.services.book_ingestion import _upsert_book, _upsert_objects, _upsert_sections
from scripts import build_book_reads


pytestmark = pytest.mark.skipif(
    os.getenv("THEUMST_BOOK_READ_DB_TESTS") != "1", reason="Explicit isolated PostgreSQL acceptance only"
)

TWO_WEEKS = "private, max-age=1209600"


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
    with disposable_database("theumst_book_read_test"):
        yield create_app(initialize_services=False)


@pytest.fixture(scope="module")
def client(application):
    return TestClient(application)


def sql_one(query, params=()):
    with database.transaction() as (_, cur):
        cur.execute(query, params)
        return cur.fetchone()


def sql_all(query, params=()):
    with database.transaction() as (_, cur):
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def account(authority):
    """A confirmed account of the given authority with a session cookie and a master key."""
    name = f"{authority}_{uuid4().hex[:10]}"
    raw = f"umst_mast_{uuid4().hex}"
    token = uuid4().hex + uuid4().hex
    with database.transaction() as (_, cur):
        cur.execute(
            """INSERT INTO "user" (username, email, password_hash, authority_id, email_verified_at)
               SELECT %s, %s, %s, authority_id, now() FROM authority WHERE name = %s RETURNING user_id""",
            (name, f"{name}@example.invalid", hash_password("unused-passphrase"), authority),
        )
        user_id = cur.fetchone()["user_id"]
        cur.execute(
            """INSERT INTO api_key (user_id, api_rate_id, name, key_prefix, key_hash, key_type)
               VALUES (%s, NULL, 'publisher', %s, %s, 'master')""",
            (user_id, raw[:16], hash_secret(raw)),
        )
        cur.execute(
            "INSERT INTO web_session (user_id, token_hash, expires_at) VALUES (%s, %s, now() + interval '1 day')",
            (user_id, hash_secret(token)),
        )
    return {"user_id": user_id, "cookie": {"Cookie": f"{get_settings().cookie_name}={token}"},
            "key": {"X-API-Key": raw}}


@pytest.fixture(scope="module")
def reader(application):
    return account("betatester")


@pytest.fixture(scope="module")
def outsider(application):
    return account("user")


@pytest.fixture(scope="module")
def publisher(application):
    return account("superadmin")


# --- books -------------------------------------------------------------------------------------

def manifest(book_key, *, extra_objects=(), extra_relations=(), shared_key="crystal-open-sets"):
    """A demo book: three sections (one nested), five objects in an order that is not their keys',
    a crystal shared inside the book and one shared with another book, dependencies, and a support."""
    objects = [
        {"source_key": "def-open", "section_source_key": "s1", "type": "definition", "label": "Open set",
         "statement": "A set is open when ...", "crystal_source_key": f"{book_key}-crystal-open",
         "source_metadata": {"order": [1], "difficulty": 35, "estimated_minutes": 0.2}},
        {"source_key": "thm-union", "section_source_key": "s1", "type": "theorem", "name": "Unions of open sets",
         "label": "Theorem 1.2", "statement": "Unions of open sets are open.", "crystal_source_key": shared_key,
         "source_metadata": {"order": [2], "difficulty": 40.5, "estimated_minutes": 1.3}},
        {"source_key": "def-open-again", "section_source_key": "s21", "type": "definition", "label": "Open set again",
         "statement": "Open, restated.", "crystal_source_key": f"{book_key}-crystal-open",
         "is_default_in_crystal": False, "source_metadata": {"order": [5], "difficulty": "hard"}},
        {"source_key": "thm-ivt", "section_source_key": "s21", "type": "theorem", "name": "Intermediate Value Theorem",
         "label": "Theorem 2.1", "statement": "A continuous ...", "source_metadata": {"order": [4], "estimated_minutes": 2}},
        {"source_key": "ex-1", "section_source_key": "s2", "type": "exercise", "label": "Exercise 2.1",
         "statement": "Show that ...", "source_metadata": {"order": [3]}},
        *extra_objects,
    ]
    roles = {"ex-1": "assessment", "def-open-again": "support"}
    relations = [
        ("def-open", "thm-union", "dependency"), ("def-open", "thm-ivt", "dependency"),
        ("thm-union", "thm-ivt", "dependency"), ("thm-ivt", "ex-1", "dependency"),
        ("thm-ivt", "thm-union", "dependency"),  # a dependency cycle, which uploads may keep
        ("def-open-again", "def-open", "supports"),
        *extra_relations,
    ]
    return {
        "schema_version": 2,
        "book": {"source_key": book_key, "title": f"Topology {book_key}", "metadata": {"demo": True}},
        "sections": [
            {"source_key": "s1", "section_number": "001", "section_name": "1 Topological spaces",
             "metadata": {"minutes": {"own": 1.5, "whole": 3.5}}},
            {"source_key": "s2", "section_number": "002", "section_name": "2 Connectedness",
             "metadata": {"minutes": {"own": "n/a", "whole": 27.4}}},
            {"source_key": "s21", "section_number": "001", "section_name": "2.1 Paths", "parent_source_key": "s2"},
        ],
        "objects": objects,
        "embeddings": [],
        "images": [],
        "knowledge_graph": {
            "contract_version": 1, "graph_revision": "r1",
            "nodes": [{"knowledge_id": f"k-{item['source_key']}", "object_source_key": item["source_key"],
                       "graph_role": roles.get(item["source_key"], "backbone")} for item in objects],
            "relations": [{"source_knowledge_id": f"k-{source}", "target_knowledge_id": f"k-{target}",
                           "relation_type": kind} for source, target, kind in relations],
        },
    }


def archive(data):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("manifest.json", json.dumps(data))
    return buffer.getvalue()


def upload(client, publisher, data):
    response = client.post("/api/v1/books/ingest-archive", headers=publisher["key"],
                           files={"archive": ("book.zip", archive(data), "application/zip")})
    assert response.status_code == 201, response.text
    return response.json()


def ids_by_key(grimoire_id):
    rows = sql_all(
        "SELECT k.source_key, k.knowledge_id FROM knowledge k JOIN section s ON s.section_id = k.section_id "
        "WHERE s.grimoire_id = %s", (grimoire_id,))
    return {row["source_key"]: row["knowledge_id"] for row in rows}


def stored_row(grimoire_id, table="book_read"):
    assert table in book_read.READS
    return sql_one(f"SELECT format, version, body_gzip, raw_bytes, object_count, built_at FROM {table} "
                   "WHERE grimoire_id = %s", (grimoire_id,))


def game_row(grimoire_id):
    return stored_row(grimoire_id, "book_game_read")


def read(client, reader, grimoire_id, **headers):
    return client.get(f"/api/demo/grimoires/{grimoire_id}/book-read", headers={**reader["cookie"], **headers})


def raw_read(client, reader, grimoire_id, **headers):
    with client.stream("GET", f"/api/demo/grimoires/{grimoire_id}/book-read",
                       headers={**reader["cookie"], **headers}) as response:
        return response, b"".join(response.iter_raw())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


@pytest.fixture(scope="module")
def book(client, publisher):
    """Two books sharing one crystal; the first is the one read."""
    other = upload(client, publisher, manifest(f"other-{uuid4().hex[:6]}"))
    receipt = upload(client, publisher, manifest(f"topology-{uuid4().hex[:6]}"))
    return {"grimoire_id": receipt["grimoire_id"], "receipt": receipt, "other": other["grimoire_id"],
            "ids": ids_by_key(receipt["grimoire_id"])}


# --- what ingestion stores is what the route returns ---------------------------------------------

def test_the_upload_stores_the_answer_the_route_returns(client, reader, book):
    receipt = book["receipt"]["book_read"]
    row = stored_row(book["grimoire_id"])
    body = gzip.decompress(bytes(row["body_gzip"]))
    assert receipt == {"format": 1, "version": row["version"], "raw_bytes": len(body),
                       "gzip_bytes": len(bytes(row["body_gzip"]))}
    assert (row["format"], row["raw_bytes"], row["object_count"]) == (1, len(body), 5)

    response, raw = raw_read(client, reader, book["grimoire_id"], **{"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert raw == bytes(row["body_gzip"])  # the stored bytes, one gzip layer
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["etag"] == f'"{row["version"]}"'
    assert response.headers["cache-control"] == TWO_WEEKS

    plain = read(client, reader, book["grimoire_id"], **{"Accept-Encoding": "identity"})
    assert plain.status_code == 200 and plain.content == body
    assert "content-encoding" not in plain.headers

    answer = json.loads(body)
    assert answer["version"] == row["version"]
    assert hashlib.sha256(canonical({k: v for k, v in answer.items() if k != "version"})).hexdigest() == row["version"]
    with database.transaction() as (_, cur):
        assert book_read.build(cur, book["grimoire_id"]).body == body  # a fresh build gives the same bytes


def test_the_answer_matches_the_knowledge_list(client, reader, book):
    answer = read(client, reader, book["grimoire_id"]).json()
    listed = client.get(f"/api/demo/grimoires/{book['grimoire_id']}/knowledge", headers=reader["cookie"])
    assert listed.status_code == 200
    rows = listed.json()["knowledge"]
    assert [item["id"] for item in answer["objects"]] == [row["knowledge_id"] for row in rows]
    for item, row in zip(answer["objects"], rows):
        for field in ("section_id", "type", "name", "label", "source_key", "difficulty", "estimated_minutes"):
            assert item[field] == row[field], field
            assert type(item[field]) is type(row[field]), field  # 40.5 stays a float, 35 an int
    ids = book["ids"]
    assert [item["id"] for item in answer["objects"]] == [
        ids[key] for key in ("def-open", "thm-union", "ex-1", "thm-ivt", "def-open-again")
    ]
    by_id = {item["id"]: item for item in answer["objects"]}
    assert by_id[ids["thm-union"]]["difficulty"] == 40.5 and by_id[ids["def-open-again"]]["difficulty"] is None
    assert by_id[ids["ex-1"]]["role"] == "assessment" and by_id[ids["def-open"]]["role"] == "backbone"
    assert by_id[ids["def-open-again"]]["crystal_default"] is False
    assert answer["graph_capability"] == "semantic_relations"
    assert answer["counts"] == {"sections": 3, "objects": 5, "shared_crystals": 1,
                                "relations": {"dependency": 5, "supports": 1}}


def test_the_sections_follow_the_contents(client, reader, book):
    answer = read(client, reader, book["grimoire_id"]).json()
    assert [(item["name"], item["depth"], item["minutes_own"], item["minutes_whole"]) for item in answer["sections"]] == [
        ("1 Topological spaces", 0, 1.5, 3.5),
        ("2 Connectedness", 0, None, 27.4),  # "n/a" is not a number
        ("2.1 Paths", 1, None, None),
    ]
    parent = answer["sections"][1]["id"]
    assert answer["sections"][2]["parent_id"] == parent and answer["sections"][2]["number"] == "001"
    contents = client.get(f"/api/demo/books/{book['grimoire_id']}", headers=reader["cookie"]).json()
    assert {item["id"] for item in answer["sections"]} == {row["section_id"] for row in contents["contents"]}


def test_the_relations_are_the_dependencies_route_and_the_supports(client, reader, book):
    answer = read(client, reader, book["grimoire_id"]).json()
    ids = book["ids"]
    dependency = answer["relations"]["dependency"]
    assert dependency == sorted(dependency)
    for item in answer["objects"]:
        response = client.get(f"/api/demo/knowledge/{item['id']}/dependencies", headers=reader["cookie"])
        assert response.status_code == 200
        uses = {row["knowledge_id"] for row in response.json()["results"]}
        assert uses == {source for source, target in dependency if target == item["id"]}, item["source_key"]
    assert answer["relations"]["supports"] == [[ids["def-open-again"], ids["def-open"]]]


def test_the_crystals_are_crystallize_restricted_to_the_book(client, reader, book):
    answer = read(client, reader, book["grimoire_id"]).json()
    ids = book["ids"]
    members = {item["id"]: item["members"] for item in answer["crystals"]}
    assert list(members.values()) == [[ids["def-open"], ids["def-open-again"]]]
    for item in answer["objects"]:
        response = client.get(f"/api/demo/crystallize/{item['id']}", headers=reader["cookie"])
        assert response.status_code == 200
        everywhere = response.json()["results"]
        here = {row["knowledge_id"] for row in everywhere if row["grimoire_id"] == book["grimoire_id"]}
        assert here == set(members.get(item["crystal_id"], [item["id"]])), item["source_key"]
        if item["id"] == ids["thm-union"]:  # its crystal reaches the other book, which the answer leaves out
            assert {row["grimoire_id"] for row in everywhere} == {book["grimoire_id"], book["other"]}
            assert item["crystal_id"] not in members


# --- ETag, 304 and the refusals ------------------------------------------------------------

def test_a_matching_etag_answers_304(client, reader, book):
    version = stored_row(book["grimoire_id"])["version"]
    for tag in (f'"{version}"', f'W/"{version}"', f'"stale", "{version}"', "*"):
        response = read(client, reader, book["grimoire_id"], **{"If-None-Match": tag})
        assert response.status_code == 304, tag
        assert response.content == b""
        assert response.headers["etag"] == f'"{version}"'
        assert response.headers["cache-control"] == TWO_WEEKS
    assert read(client, reader, book["grimoire_id"], **{"If-None-Match": '"stale"'}).status_code == 200


def test_without_a_session_the_route_answers_401(client, book):
    response = client.get(f"/api/demo/grimoires/{book['grimoire_id']}/book-read")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert response.headers["cache-control"] == "no-store"


def test_an_account_without_web_demo_access_gets_403(client, outsider, book):
    response = read(client, outsider, book["grimoire_id"])
    assert response.status_code == 403
    assert response.json() == {"detail": "Access to demo is not permitted"}


def test_a_missing_book_answers_404(client, reader):
    response = read(client, reader, 2_000_000_000)
    assert response.status_code == 404
    assert response.json() == {"detail": "Demo grimoire not found", "code": "book_not_found"}
    assert response.headers["cache-control"] == "no-store"


def test_a_hidden_book_answers_404_and_comes_back_unchanged(client, reader, publisher):
    receipt = upload(client, publisher, manifest(f"hidden-{uuid4().hex[:6]}"))
    grimoire_id = receipt["grimoire_id"]
    before = stored_row(grimoire_id)
    with database.transaction() as (_, cur):
        cur.execute("UPDATE grimoire SET source_metadata = source_metadata || '{\"demo\": false}' WHERE grimoire_id = %s",
                    (grimoire_id,))
    response = read(client, reader, grimoire_id)
    assert response.status_code == 404 and response.json()["code"] == "book_not_found"
    with database.transaction() as (_, cur):
        cur.execute("UPDATE grimoire SET source_metadata = source_metadata || '{\"demo\": true}' WHERE grimoire_id = %s",
                    (grimoire_id,))
    after = read(client, reader, grimoire_id)
    assert after.status_code == 200 and after.headers["etag"] == f'"{before["version"]}"'
    assert stored_row(grimoire_id)["built_at"] == before["built_at"]  # hiding rebuilt nothing


def test_a_book_built_before_its_read_answers_409(client, reader):
    with database.transaction() as (_, cur):
        grimoire_id, language_id = _upsert_book(cur, {"source_key": f"direct-{uuid4().hex[:6]}", "title": "Direct",
                                                      "metadata": {"demo": True}})
        sections = _upsert_sections(cur, grimoire_id, language_id, [{"source_key": "one", "section_number": "1"}])
        _upsert_objects(cur, grimoire_id=grimoire_id, language_id=language_id, sections=sections,
                        objects=[{"source_key": "a", "section_source_key": "one", "type": "theorem", "statement": "A"}])
    response = read(client, reader, grimoire_id)
    assert response.status_code == 409
    assert response.json() == {"detail": "This book's whole read has not been computed yet",
                               "code": "book_read_not_computed"}
    assert response.headers["cache-control"] == "no-store"
    assert build_book_reads.run([grimoire_id], out=io.StringIO()) == 0
    assert read(client, reader, grimoire_id).status_code == 200


def test_the_route_does_not_mark_the_book_opened_and_summon_does(client, book):
    newcomer = account("betatester")
    assert read(client, newcomer, book["grimoire_id"]).status_code == 200
    opened = "SELECT last_opened_at FROM user_grimoire WHERE user_id = %s AND grimoire_id = %s"
    assert sql_one(opened, (newcomer["user_id"], book["grimoire_id"])) is None
    summoned = client.post(f"/api/demo/grimoires/{book['grimoire_id']}/summon", headers=newcomer["cookie"])
    assert summoned.status_code == 200
    assert sql_one(opened, (newcomer["user_id"], book["grimoire_id"])) is not None


# --- what changes the version ---------------------------------------------------------------

def test_a_re_upload_changes_the_version_and_an_unchanged_one_does_not(client, reader, publisher):
    key = f"reupload-{uuid4().hex[:6]}"
    first = upload(client, publisher, manifest(key))
    grimoire_id = first["grimoire_id"]
    old = stored_row(grimoire_id)

    same = upload(client, publisher, manifest(key))
    assert same["book_read"] == first["book_read"]
    assert stored_row(grimoire_id)["built_at"] == old["built_at"]  # an unchanged version writes nothing

    changed = upload(client, publisher, manifest(
        key,
        extra_objects=[{"source_key": "cor-1", "section_source_key": "s21", "type": "corollary", "label": "Cor 2.2",
                        "statement": "So ...", "source_metadata": {"order": [6], "difficulty": 50}}],
        extra_relations=[("thm-ivt", "cor-1", "dependency")],
    ))
    assert changed["grimoire_id"] == grimoire_id
    new = stored_row(grimoire_id)
    assert changed["book_read"]["version"] == new["version"] != old["version"]
    assert new["object_count"] == 6

    stale = read(client, reader, grimoire_id, **{"If-None-Match": f'"{old["version"]}"'})
    assert stale.status_code == 200 and stale.headers["etag"] == f'"{new["version"]}"'
    answer = stale.json()
    assert answer["objects"][-1]["source_key"] == "cor-1"
    assert answer["counts"]["relations"]["dependency"] == 6

    # Dropping the object again deactivates it; its arrows leave the answer with it.
    back = upload(client, publisher, manifest(key))
    assert back["book_read"]["version"] == old["version"]


def test_a_single_object_submission_changes_the_version(client, reader, publisher):
    receipt = upload(client, publisher, manifest(f"submit-{uuid4().hex[:6]}"))
    grimoire_id = receipt["grimoire_id"]
    old = stored_row(grimoire_id)["version"]
    section_id = sql_one("SELECT section_id FROM section WHERE grimoire_id = %s AND source_key = 's1'",
                         (grimoire_id,))["section_id"]
    response = client.post("/api/v1/knowledge", headers=publisher["key"], json={
        "book": {"grimoire_id": grimoire_id}, "section": {"section_id": section_id},
        "knowledge": {"type": "remark", "name": "A late remark", "statement": "Note that ..."},
    })
    assert response.status_code == 201, response.text
    new = stored_row(grimoire_id)["version"]
    assert new != old
    answer = read(client, reader, grimoire_id).json()
    assert answer["version"] == new
    assert answer["objects"][-1]["id"] == response.json()["knowledge_id"]
    assert answer["objects"][-1]["label"] == "A late remark"


def test_deleting_a_book_deletes_its_row(client, publisher):
    receipt = upload(client, publisher, manifest(f"deleted-{uuid4().hex[:6]}"))
    assert stored_row(receipt["grimoire_id"])
    with database.transaction() as (_, cur):
        cur.execute("DELETE FROM grimoire WHERE grimoire_id = %s", (receipt["grimoire_id"],))
    assert stored_row(receipt["grimoire_id"]) is None


def test_a_failed_build_deletes_the_row_and_the_upload_still_succeeds(client, reader, publisher, monkeypatch):
    key = f"failing-{uuid4().hex[:6]}"
    grimoire_id = upload(client, publisher, manifest(key))["grimoire_id"]
    assert stored_row(grimoire_id)

    def broken(cur, grimoire_id):
        cur.execute("SELECT 1/0")  # a database error, which aborts the transaction up to the savepoint

    monkeypatch.setattr(book_read, "build", broken)
    receipt = upload(client, publisher, manifest(
        key, extra_objects=[{"source_key": "late", "section_source_key": "s1", "type": "remark",
                             "statement": "Late.", "source_metadata": {"order": [9]}}],
    ))
    monkeypatch.undo()
    assert set(receipt["book_read"]) == {"error"} and "division by zero" in receipt["book_read"]["error"]
    assert stored_row(grimoire_id) is None
    assert read(client, reader, grimoire_id).json()["code"] == "book_read_not_computed"
    # The upload itself committed: the new object is in the book.
    listed = client.get(f"/api/demo/grimoires/{grimoire_id}/knowledge", headers=reader["cookie"]).json()
    assert [row["source_key"] for row in listed["knowledge"]][-1] == "late"


def test_writers_of_one_book_share_one_lock(book):
    holder = database.connect()
    try:
        with holder.cursor() as cur:
            book_read.lock(cur, book["grimoire_id"])
            with database.transaction() as (_, other):
                other.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s), %s) AS got",
                              (book_read.LOCK_NAME, book["grimoire_id"]))
                assert other.fetchone()["got"] is False
                other.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s), %s) AS got",
                              (book_read.LOCK_NAME, book["other"]))
                assert other.fetchone()["got"] is True
            # The manual run waits for the holder, then writes nothing new.
            done = threading.Event()
            codes = []
            worker = threading.Thread(target=lambda: (codes.append(
                build_book_reads.run([book["grimoire_id"]], out=io.StringIO())), done.set()))
            worker.start()
            assert not done.wait(0.5)
        holder.rollback()
        worker.join(10)
        assert codes == [0]
    finally:
        holder.close()


# --- the operator command -----------------------------------------------------------------

def test_the_command_run_twice_changes_nothing_the_second_time(client, publisher, book):
    hidden = upload(client, publisher, manifest(f"hidden-cmd-{uuid4().hex[:6]}"))["grimoire_id"]
    with database.transaction() as (_, cur):
        cur.execute("UPDATE grimoire SET source_metadata = source_metadata || '{\"demo\": false}' WHERE grimoire_id = %s",
                    (hidden,))
    uploaded = {table: {row["grimoire_id"]: row["version"]
                        for row in sql_all(f"SELECT grimoire_id, version FROM {table}")}
                for table in book_read.READS}
    with database.transaction() as (_, cur):
        cur.execute("DELETE FROM book_read")
        cur.execute("DELETE FROM book_game_read")
    books = [row["grimoire_id"] for row in sql_all("SELECT grimoire_id FROM grimoire ORDER BY grimoire_id")]

    first = io.StringIO()
    assert build_book_reads.run(out=first) == 0
    lines = first.getvalue().splitlines()
    assert lines[0] == "book_read format 1; book_game_read format 1"
    # every book, hidden ones too, in id order, a line per row
    assert [(int(line.split()[1]), line.split()[2]) for line in lines[1:-1]] == [
        (grimoire_id, table) for grimoire_id in books for table in book_read.READS
    ]
    assert all(line.split()[-3] == "written" for line in lines[1:-1])
    assert lines[-1].startswith(f"{len(books)} books: book_read {len(books)} written, 0 unchanged, 0 failed; "
                                f"book_game_read {len(books)} written, 0 unchanged, 0 failed; ")
    rows = {table: {row["grimoire_id"]: row for row in sql_all(f"SELECT * FROM {table}")} for table in book_read.READS}
    for table in book_read.READS:
        assert set(rows[table]) == set(books)
        for grimoire_id, version in uploaded[table].items():
            assert rows[table][grimoire_id]["version"] == version  # the same facts give ingestion's version

    second = io.StringIO()
    assert build_book_reads.run(out=second) == 0
    assert all(line.split()[-3] == "unchanged" for line in second.getvalue().splitlines()[1:-1])
    assert second.getvalue().splitlines()[-1].startswith(
        f"{len(books)} books: book_read 0 written, {len(books)} unchanged, 0 failed; "
        f"book_game_read 0 written, {len(books)} unchanged, 0 failed; ")
    for table in book_read.READS:
        again = {row["grimoire_id"]: row for row in sql_all(f"SELECT * FROM {table}")}
        for grimoire_id, row in rows[table].items():
            assert again[grimoire_id]["built_at"] == row["built_at"]
            assert bytes(again[grimoire_id]["body_gzip"]) == bytes(row["body_gzip"])

    check = io.StringIO()
    assert build_book_reads.run(check=True, out=check) == 0
    assert all(line.split()[-3] == "current" for line in check.getvalue().splitlines()[1:-1])


def test_the_check_finds_stale_and_missing_books_and_writes_nothing(book):
    with database.transaction() as (_, cur):
        cur.execute("UPDATE book_read SET version = repeat('0', 64) WHERE grimoire_id = %s", (book["grimoire_id"],))
        cur.execute("DELETE FROM book_read WHERE grimoire_id = %s", (book["other"],))
        cur.execute("DELETE FROM book_game_read WHERE grimoire_id = %s", (book["grimoire_id"],))
    out = io.StringIO()
    assert build_book_reads.run([book["grimoire_id"], book["other"]], check=True, out=out) == 2
    words = {(int(line.split()[1]), line.split()[2]): line.split()[-3] for line in out.getvalue().splitlines()[1:-1]}
    assert words == {
        (book["grimoire_id"], "book_read"): "stale", (book["grimoire_id"], "book_game_read"): "missing",
        (book["other"], "book_read"): "missing", (book["other"], "book_game_read"): "current",
    }
    assert stored_row(book["other"]) is None and game_row(book["grimoire_id"]) is None
    assert stored_row(book["grimoire_id"])["version"] == "0" * 64

    assert build_book_reads.run([book["grimoire_id"], book["other"]], out=io.StringIO()) == 0
    assert build_book_reads.run(check=True, out=io.StringIO()) == 0
    out = io.StringIO()
    assert build_book_reads.run([2_000_000_000], out=out) == 1
    assert "book 2000000000  failed: no such book" in out.getvalue()


# --- migration 016 -----------------------------------------------------------------------------

def catalogue(cur):
    cur.execute(
        """SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'book_read' ORDER BY ordinal_position"""
    )
    columns = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint
           WHERE conrelid = 'book_read'::regclass ORDER BY 1"""
    )
    return columns, [row["definition"] for row in cur.fetchall()]


def test_migration_016_brings_a_0_0_14_database_to_the_fresh_schema_and_can_run_again():
    with disposable_database("theumst_migration_016_test"):
        with database.transaction() as (_, cur):
            fresh = catalogue(cur)
            # The database as 0.0.14 left it, holding a demo book.
            cur.execute("DROP TABLE book_read")
            grimoire_id, language_id = _upsert_book(cur, {"source_key": "kept", "title": "Kept",
                                                          "metadata": {"demo": True}})
            sections = _upsert_sections(cur, grimoire_id, language_id, [{"source_key": "one", "section_number": "1"}])
            _upsert_objects(cur, grimoire_id=grimoire_id, language_id=language_id, sections=sections,
                            objects=[{"source_key": "a", "section_source_key": "one", "type": "theorem",
                                      "statement": "A"}])
        with pytest.raises(reviewed_migrations.MigrationSafetyError, match="book_read_v1"):
            reviewed_migrations.assert_database_schema_ready()

        first = reviewed_migrations.apply_reviewed_migrations(backup_sha256="0" * 64)
        actions = {entry["migration"]: entry["action"] for entry in first["migrations"]}
        assert actions.pop("book_read_v1") == "applied"
        assert set(actions.values()) == {"already_applied"}
        reviewed_migrations.assert_database_schema_ready()
        with database.transaction() as (_, cur):
            assert catalogue(cur) == fresh
            cur.execute("SELECT count(*) AS n FROM book_read")
            assert cur.fetchone()["n"] == 0  # 016 writes no rows
            source = next(path for migration, path in reviewed_migrations.validated_migration_sources()
                          if migration.key == "book_read_v1")
            cur.execute(source.read_text(encoding="utf-8"))  # it can run again
            assert catalogue(cur) == fresh

        again = reviewed_migrations.apply_reviewed_migrations(backup_sha256="0" * 64)
        assert {entry["action"] for entry in again["migrations"]} == {"already_applied"}
        assert build_book_reads.run(out=io.StringIO()) == 0
        assert sql_one("SELECT object_count FROM book_read WHERE grimoire_id = %s", (grimoire_id,))["object_count"] == 1
    assert [column["column_name"] for column in fresh[0]] == [
        "grimoire_id", "format", "version", "body_gzip", "raw_bytes", "object_count", "built_at",
    ]
    assert "FOREIGN KEY (grimoire_id) REFERENCES grimoire(grimoire_id) ON DELETE CASCADE" in fresh[1]


# --- the game's whole-book read (0.0.16) -------------------------------------------------------

INSTALL = "pg-test-install"


def game_key(owner):
    """A regular key at the standard tier, as the game's sign-in makes one."""
    with database.transaction() as (_, cur):
        issued = create_regular_key(cur, owner["user_id"], "UMST · PG test", client="umst")
    return {"headers": {"X-API-Key": issued["key"], "X-Install-Id": INSTALL}, "api_key_id": issued["api_key_id"],
            "user_id": owner["user_id"]}


@pytest.fixture(scope="module")
def player(reader):
    return game_key(reader)


@pytest.fixture(scope="module")
def stranger(outsider):
    return game_key(outsider)


def game_get(client, key, path, **headers):
    return client.get(path, headers={**key["headers"], **headers})


def usage(key):
    rows = sql_all("SELECT kind, sum(request_count)::int AS n FROM api_usage_daily WHERE api_key_id = %s GROUP BY kind",
                   (key["api_key_id"],))
    return {row["kind"]: row["n"] for row in rows}


def image(grimoire_id, section_id, source_image_id, knowledge_ids, link_type, **metadata):
    """An image row as ingestion's _store_images hands it to _finalize_images."""
    return {
        "section_id": section_id,
        "knowledge_id": knowledge_ids[0] if knowledge_ids and link_type == "figure" else None,
        "source_image_id": source_image_id, "semantic_context_name": f"{link_type} {source_image_id}",
        "storage_key": f"books/{grimoire_id}/{link_type}s/{source_image_id} scan.png",
        "url": f"https://bucket.invalid/{source_image_id}", "metadata": metadata,
        "link_type": link_type, "knowledge_ids": knowledge_ids,
    }


@pytest.fixture(scope="module")
def illustrated(client, publisher):
    """A book with figures and page scans, written by ingestion's own _finalize_images."""
    receipt = upload(client, publisher, manifest(f"illustrated-{uuid4().hex[:6]}"))
    grimoire_id = receipt["grimoire_id"]
    ids = ids_by_key(grimoire_id)
    section = sql_one("SELECT section_id FROM section WHERE grimoire_id = %s AND source_key = 's1'",
                      (grimoire_id,))["section_id"]
    uploaded = game_row(grimoire_id)
    counts, result = book_ingestion._finalize_images([
        image(grimoire_id, section, "fig-a", [ids["def-open"], ids["thm-union"]], "figure", page=3),
        image(grimoire_id, section, "fig-legacy", [ids["thm-ivt"]], "figure"),
        image(grimoire_id, section, "fig-old", [ids["def-open"]], "figure", page=1),
        # In book_image_id order p-4 comes before p-3; in page order after it.
        image(grimoire_id, section, "p-4", [ids["def-open"], ids["thm-union"]], "page", page=4, printed_page=2),
        image(grimoire_id, section, "p-3", [ids["def-open"]], "page", page=3, printed_page="1"),
        image(grimoire_id, section, "p-x", [ids["ex-1"]], "page", printed_page=["?"]),
    ], grimoire_id)
    finalized = game_row(grimoire_id)
    # A figure an upload before migration 012 named only in book_image.knowledge_id, and one no longer active.
    with database.transaction() as (_, cur):
        cur.execute(
            """DELETE FROM book_image_knowledge WHERE book_image_id =
               (SELECT book_image_id FROM book_image WHERE grimoire_id = %s AND source_image_id = 'fig-legacy')""",
            (grimoire_id,))
        cur.execute("UPDATE book_image SET is_active = false WHERE grimoire_id = %s AND source_image_id = 'fig-old'",
                    (grimoire_id,))
    assert build_book_reads.run([grimoire_id], out=io.StringIO()) == 0
    return {"grimoire_id": grimoire_id, "ids": ids, "receipt": receipt, "uploaded": uploaded,
            "finalized": finalized, "counts": counts, "result": result}


def game_book(client, key, grimoire_id, **headers):
    return game_get(client, key, f"/api/game/grimoires/{grimoire_id}/book", **headers)


def test_an_upload_stores_the_game_answer_the_route_returns(client, player, book):
    receipt = book["receipt"]["book_game_read"]
    row = game_row(book["grimoire_id"])
    body = gzip.decompress(bytes(row["body_gzip"]))
    assert receipt == {"format": 1, "version": row["version"], "raw_bytes": len(body),
                       "gzip_bytes": len(bytes(row["body_gzip"]))}
    assert (row["format"], row["raw_bytes"], row["object_count"]) == (1, len(body), 5)
    with client.stream("GET", f"/api/game/grimoires/{book['grimoire_id']}/book",
                       headers={**player["headers"], "Accept-Encoding": "gzip"}) as response:
        raw = b"".join(response.iter_raw())
    assert response.status_code == 200 and raw == bytes(row["body_gzip"])
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["etag"] == f'"{row["version"]}"'
    assert response.headers["cache-control"] == TWO_WEEKS
    assert {token.strip() for token in response.headers["vary"].split(",")} == {
        "X-API-Key", "Authorization", "Accept-Encoding"}
    with database.transaction() as (_, cur):
        assert book_read.build_game(cur, book["grimoire_id"]).body == body  # a fresh build gives the same bytes


def test_the_game_answer_is_the_web_demos_with_each_objects_route(client, reader, player, illustrated):
    grimoire_id = illustrated["grimoire_id"]
    game = game_book(client, player, grimoire_id).json()
    web = read(client, reader, grimoire_id).json()
    for key in ("format", "grimoire_id", "graph_capability", "sections", "relations", "crystals"):
        assert game[key] == web[key], key
    assert {key: value for key, value in game["counts"].items() if key not in ("figures", "pages")} == web["counts"]
    assert [item["id"] for item in game["objects"]] == [item["id"] for item in web["objects"]]
    for item, plain in zip(game["objects"], web["objects"]):
        assert {key: item[key] for key in plain} == plain
        one = client.get(f"/api/demo/grimoires/{grimoire_id}/knowledge/{item['id']}", headers=reader["cookie"])
        assert one.status_code == 200
        knowledge = one.json()["knowledge"]
        for field in ("statement", "working", "working_summary"):
            assert item[field] == knowledge[field], field
        assert item["figures"] == [
            {"image": row["source_image_id"], "url": row["url"], "caption": row["semantic_context_name"],
             "page": row["metadata"].get("page") if isinstance(row["metadata"].get("page"), int) else None,
             "updated_at": item["figures"][index]["updated_at"]}
            for index, row in enumerate(knowledge["images"])
        ]
        assert item["pages"] == [row["source_image_id"] for row in knowledge["pages"]]
        for row in knowledge["pages"]:
            entry = game["pages"][row["source_image_id"]]
            assert entry["url"] == row["url"]
            assert entry["page"] == row["metadata"].get("page")
    ids = illustrated["ids"]
    by_id = {item["id"]: item for item in game["objects"]}
    assert [figure["image"] for figure in by_id[ids["def-open"]]["figures"]] == ["fig-a"]  # fig-old is inactive
    assert [figure["image"] for figure in by_id[ids["thm-union"]]["figures"]] == ["fig-a"]
    assert [figure["image"] for figure in by_id[ids["thm-ivt"]]["figures"]] == ["fig-legacy"]
    assert by_id[ids["def-open"]]["pages"] == ["p-3", "p-4"]  # page order, not id order
    assert by_id[ids["thm-union"]]["pages"] == ["p-4"] and by_id[ids["ex-1"]]["pages"] == ["p-x"]
    assert by_id[ids["def-open"]]["figures"][0]["url"] == f"/api/v1/storage/books/{grimoire_id}/figures/fig-a%20scan.png"
    assert {key: (value["page"], value["printed_page"]) for key, value in game["pages"].items()} == {
        "p-3": (3, "1"), "p-4": (4, 2), "p-x": (None, None),
    }
    assert all(value["updated_at"].endswith("Z") for value in game["pages"].values())
    assert game["counts"]["figures"] == 3 and game["counts"]["pages"] == 3
    assert by_id[ids["def-open"]]["statement"] == "A set is open when ..."
    assert by_id[ids["def-open"]]["working"] == "" and by_id[ids["def-open"]]["working_summary"] is None


def test_finalizing_the_images_gives_the_game_a_new_version(illustrated):
    assert illustrated["counts"] == {"figure": 4, "page": 4}
    assert illustrated["result"].status == "written"
    assert illustrated["finalized"]["version"] == illustrated["result"].built.version != illustrated["uploaded"]["version"]
    # An unchanged rebuild writes nothing.
    out = io.StringIO()
    assert build_book_reads.run([illustrated["grimoire_id"]], out=out) == 0
    assert [line.split()[-3] for line in out.getvalue().splitlines()[1:-1]] == ["unchanged", "unchanged"]


def test_a_page_scan_comes_through_the_game_key_and_counts_as_a_book_read(client, player, stranger, illustrated,
                                                                            monkeypatch):
    url = game_book(client, player, illustrated["grimoire_id"]).json()["pages"]["p-3"]["url"]
    monkeypatch.setattr(storage, "read_bytes", lambda key: b"\xff\xd8 scan of " + key.encode())
    before = usage(player).get("book", 0)
    response = client.get(url, headers=player["headers"])
    assert response.status_code == 200, response.text
    assert response.content == f"\xff\xd8 scan of books/{illustrated['grimoire_id']}/pages/p-3 scan.png".encode("latin-1")
    assert usage(player)["book"] == before + 1
    refused = client.get(url, headers=stranger["headers"])
    assert refused.status_code == 403 and refused.json()["code"] == "demo_access_required"
    assert client.get(url).status_code == 401


@pytest.mark.parametrize("tag", ['"{v}"', 'W/"{v}"', '"stale", "{v}"', "*"])
def test_the_kept_version_answers_304(client, player, book, tag):
    version = game_row(book["grimoire_id"])["version"]
    response = game_book(client, player, book["grimoire_id"], **{"If-None-Match": tag.format(v=version)})
    assert response.status_code == 304 and response.content == b""
    assert response.headers["etag"] == f'"{version}"' and response.headers["cache-control"] == TWO_WEEKS
    assert game_book(client, player, book["grimoire_id"], **{"If-None-Match": '"stale"'}).status_code == 200


def test_the_book_refusals(client, player, stranger, publisher, book):
    grimoire_id = book["grimoire_id"]
    counted = usage(stranger)
    for response, status, code in [
        (client.get(f"/api/game/grimoires/{grimoire_id}/book"), 401, "invalid_key"),
        (client.get(f"/api/game/grimoires/{grimoire_id}/book", headers={"X-API-Key": "umst_read_unknown"}),
         401, "invalid_key"),
        (client.get(f"/api/game/grimoires/{grimoire_id}/book", headers=publisher["key"]), 403, "master_key_not_allowed"),
        (game_book(client, stranger, grimoire_id), 403, "demo_access_required"),
        (game_book(client, player, 2_000_000_000), 404, "book_not_found"),
        (client.get(f"/api/game/grimoires/{grimoire_id}/book", headers={**player["headers"], "X-Install-Id": "a b"}),
         422, "invalid_request"),
    ]:
        assert response.status_code == status, response.text
        assert response.json()["code"] == code
        assert response.headers["cache-control"] == "no-store"
    assert usage(stranger) == counted  # refused before anything was counted


def test_a_hidden_book_is_404_and_absent_from_the_list(client, player, publisher):
    grimoire_id = upload(client, publisher, manifest(f"hidden-game-{uuid4().hex[:6]}"))["grimoire_id"]
    with database.transaction() as (_, cur):
        cur.execute("UPDATE grimoire SET source_metadata = source_metadata || '{\"demo\": false}' WHERE grimoire_id = %s",
                    (grimoire_id,))
    response = game_book(client, player, grimoire_id)
    assert response.status_code == 404 and response.json()["code"] == "book_not_found"
    listed = game_get(client, player, "/api/game/grimoires").json()["grimoires"]
    assert grimoire_id not in {row["grimoire_id"] for row in listed}
    notes = game_get(client, player, f"/api/game/grimoires/{grimoire_id}/notes")
    assert notes.status_code == 404 and notes.json()["code"] == "book_not_found"


def test_a_book_before_its_build_answers_409_and_lists_no_version(client, player):
    with database.transaction() as (_, cur):
        grimoire_id, language_id = _upsert_book(cur, {"source_key": f"unbuilt-{uuid4().hex[:6]}",
                                                      "title": "Unbuilt (Somebody, 2024)", "metadata": {"demo": True}})
        sections = _upsert_sections(cur, grimoire_id, language_id, [{"source_key": "one", "section_number": "1"}])
        _upsert_objects(cur, grimoire_id=grimoire_id, language_id=language_id, sections=sections,
                        objects=[{"source_key": "a", "section_source_key": "one", "type": "theorem", "statement": "A"}])
    response = game_book(client, player, grimoire_id)
    assert response.status_code == 409 and response.json()["code"] == "book_read_not_computed"
    listed = {row["grimoire_id"]: row for row in game_get(client, player, "/api/game/grimoires").json()["grimoires"]}
    assert listed[grimoire_id] == {"grimoire_id": grimoire_id, "title": "Unbuilt (Somebody, 2024)",
                                   "author": "Somebody", "version": None, "objects": None, "bytes": None,
                                   "may_read": True}
    assert build_book_reads.run([grimoire_id], out=io.StringIO()) == 0
    assert game_book(client, player, grimoire_id).status_code == 200


def test_a_book_with_no_objects_is_an_empty_answer(client, player):
    with database.transaction() as (_, cur):
        grimoire_id, language_id = _upsert_book(cur, {"source_key": f"empty-{uuid4().hex[:6]}", "title": "Empty",
                                                      "metadata": {"demo": True}})
        _upsert_sections(cur, grimoire_id, language_id, [{"source_key": "one", "section_number": "1"}])
    assert build_book_reads.run([grimoire_id], out=io.StringIO()) == 0
    answer = game_book(client, player, grimoire_id).json()
    assert answer["objects"] == [] and answer["pages"] == {} and answer["counts"]["objects"] == 0
    assert len(answer["sections"]) == 1
    listed = {row["grimoire_id"]: row for row in game_get(client, player, "/api/game/grimoires").json()["grimoires"]}
    assert listed[grimoire_id]["objects"] == 0 and listed[grimoire_id]["author"] is None


def test_the_list_says_who_may_read_and_matches_the_stored_rows(client, player, stranger, book, illustrated):
    response = game_get(client, player, "/api/game/grimoires")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["may_read"] is True
    ids = [row["grimoire_id"] for row in body["grimoires"]]
    assert ids == sorted(ids)
    visible = {row["grimoire_id"] for row in sql_all(
        "SELECT grimoire_id FROM grimoire WHERE source_metadata->>'demo' = 'true'")}
    assert set(ids) == visible
    for grimoire_id in (book["grimoire_id"], illustrated["grimoire_id"]):
        row = next(item for item in body["grimoires"] if item["grimoire_id"] == grimoire_id)
        stored = game_row(grimoire_id)
        assert (row["version"], row["objects"], row["bytes"]) == (
            stored["version"], stored["object_count"], len(bytes(stored["body_gzip"])))
        assert row["title"].startswith("Topology ") and row["author"] is None and row["may_read"] is True
    other = game_get(client, stranger, "/api/game/grimoires").json()
    assert other["may_read"] is False and {row["may_read"] for row in other["grimoires"]} == {False}
    assert [row["grimoire_id"] for row in other["grimoires"]] == ids


def test_book_calls_count_as_book_reads_and_never_as_character_calls(client, reader, book):
    key = game_key(reader)
    game_get(client, key, "/api/game/grimoires")
    game_book(client, key, book["grimoire_id"])
    game_get(client, key, f"/api/game/grimoires/{book['grimoire_id']}/notes")
    assert usage(key) == {"book": 3}
    game_get(client, key, "/api/game/me")
    assert usage(key) == {"book": 3, "character": 1}


def test_a_re_upload_and_a_submission_give_the_game_a_new_version(client, player, publisher, illustrated):
    grimoire_id = illustrated["grimoire_id"]
    before = game_row(grimoire_id)["version"]
    key = illustrated["receipt"]["book_source_key"]
    again = upload(client, publisher, manifest(key))  # no images: the scans are no longer active
    assert again["grimoire_id"] == grimoire_id
    after = game_row(grimoire_id)["version"]
    assert again["book_game_read"]["version"] == after != before
    answer = game_book(client, player, grimoire_id, **{"If-None-Match": f'"{before}"'}).json()
    assert answer["pages"] == {} and all(item["figures"] == [] for item in answer["objects"])

    section_id = sql_one("SELECT section_id FROM section WHERE grimoire_id = %s AND source_key = 's1'",
                         (grimoire_id,))["section_id"]
    response = client.post("/api/v1/knowledge", headers=publisher["key"], json={
        "book": {"grimoire_id": grimoire_id}, "section": {"section_id": section_id},
        "knowledge": {"type": "remark", "name": "A late remark", "statement": "Note that $x$."},
    })
    assert response.status_code == 201, response.text
    assert game_row(grimoire_id)["version"] != after
    last = game_book(client, player, grimoire_id).json()["objects"][-1]
    assert (last["id"], last["statement"], last["working"]) == (response.json()["knowledge_id"], "Note that $x$.", "")


def test_a_failed_game_build_removes_only_its_row(client, player, reader, publisher, monkeypatch):
    key = f"game-failing-{uuid4().hex[:6]}"
    grimoire_id = upload(client, publisher, manifest(key))["grimoire_id"]
    assert game_row(grimoire_id)

    def broken(cur, grimoire_id):
        cur.execute("SELECT 1/0")

    monkeypatch.setattr(book_read, "build_game", broken)
    receipt = upload(client, publisher, manifest(
        key, extra_objects=[{"source_key": "late", "section_source_key": "s1", "type": "remark",
                             "statement": "Late.", "source_metadata": {"order": [9]}}],
    ))
    monkeypatch.undo()
    assert set(receipt["book_game_read"]) == {"error"} and "division by zero" in receipt["book_game_read"]["error"]
    assert set(receipt["book_read"]) == {"format", "version", "raw_bytes", "gzip_bytes"}
    assert game_row(grimoire_id) is None and stored_row(grimoire_id)
    assert game_book(client, player, grimoire_id).json()["code"] == "book_read_not_computed"
    assert read(client, reader, grimoire_id).status_code == 200


# --- the game's notes (0.0.16) ---------------------------------------------------------------

def notes_path(grimoire_id, note_id=None):
    return f"/api/game/grimoires/{grimoire_id}/notes" + (f"/{note_id}" if note_id is not None else "")


def test_a_note_made_in_the_game_is_the_web_demos_and_one_made_there_is_the_games(client, reader, player, book):
    grimoire_id, ids = book["grimoire_id"], book["ids"]
    made = client.post(notes_path(grimoire_id), headers=player["headers"], json={
        "knowledge_id": ids["thm-union"], "note_type": "attached", "tag": " unions ",
        "content": "By $\\bigcup_i U_i$.\nDone.",
    })
    assert made.status_code == 201, made.text
    note = made.json()["note"]
    assert note["tag"] == "unions" and note["grimoire_id"] == grimoire_id
    web = client.get("/api/demo/notes", params={"grimoire_id": grimoire_id}, headers=reader["cookie"]).json()["notes"]
    there = next(row for row in web if row["demo_note_id"] == note["demo_note_id"])
    assert (there["content"], there["tag"], there["knowledge_id"]) == (note["content"], "unions", ids["thm-union"])

    assert client.post(f"/api/demo/grimoires/{grimoire_id}/summon", headers=reader["cookie"]).status_code == 200
    web_made = client.post("/api/demo/notes", headers=reader["cookie"], json={
        "grimoire_id": grimoire_id, "knowledge_id": ids["def-open"], "note_type": "attached", "content": "On the website",
    })
    assert web_made.status_code == 201, web_made.text
    listed = client.get(notes_path(grimoire_id), headers=player["headers"])
    assert listed.status_code == 200 and listed.headers["cache-control"] == "no-store"
    rows = listed.json()["notes"]
    assert rows[0]["demo_note_id"] == web_made.json()["note"]["demo_note_id"]  # most recently changed first
    assert rows[0]["content"] == "On the website"
    assert note["demo_note_id"] in {row["demo_note_id"] for row in rows}
    stored = sql_all("SELECT demo_note_id FROM demo_note WHERE user_id = %s AND grimoire_id = %s "
                     "ORDER BY updated_at DESC, demo_note_id DESC", (reader["user_id"], grimoire_id))
    assert [row["demo_note_id"] for row in rows] == [row["demo_note_id"] for row in stored]


def test_a_game_note_does_not_add_the_book_to_my_grimoires(client, book):
    newcomer = account("betatester")
    key = game_key(newcomer)
    made = client.post(notes_path(book["grimoire_id"]), headers=key["headers"],
                       json={"note_type": "scribble", "content": "a scribble"})
    assert made.status_code == 201, made.text
    assert sql_one("SELECT 1 AS x FROM user_grimoire WHERE user_id = %s AND grimoire_id = %s",
                   (newcomer["user_id"], book["grimoire_id"])) is None


def test_the_edit_token_round_trips_through_postgresql(client, player, book):
    grimoire_id = book["grimoire_id"]
    note = client.post(notes_path(grimoire_id), headers=player["headers"],
                       json={"note_type": "scribble", "content": "first"}).json()["note"]
    stored = sql_one("SELECT updated_at FROM demo_note WHERE demo_note_id = %s", (note["demo_note_id"],))["updated_at"]
    assert note["updated_at"] == stored.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    tokens = [note["updated_at"]]
    for text in ("second", "third"):  # each answer's updated_at is the next call's token
        response = client.put(notes_path(grimoire_id, note["demo_note_id"]), headers=player["headers"],
                              json={"tag": "t", "content": text, "if_updated_at": tokens[-1]})
        assert response.status_code == 200, response.text
        tokens.append(response.json()["note"]["updated_at"])
    assert len(set(tokens)) == 3
    stale = client.put(notes_path(grimoire_id, note["demo_note_id"]), headers=player["headers"],
                       json={"tag": "t", "content": "from an old read", "if_updated_at": tokens[0]})
    assert stale.status_code == 409 and stale.json()["code"] == "note_changed"
    assert stale.json()["note"]["content"] == "third" and stale.json()["note"]["updated_at"] == tokens[-1]
    gone = client.request("DELETE", notes_path(grimoire_id, note["demo_note_id"]), headers=player["headers"],
                          json={"if_updated_at": tokens[1]})
    assert gone.status_code == 409
    deleted = client.request("DELETE", notes_path(grimoire_id, note["demo_note_id"]), headers=player["headers"],
                             json={"if_updated_at": tokens[-1]})
    assert deleted.json() == {"deleted": True, "demo_note_id": note["demo_note_id"]}
    assert sql_one("SELECT 1 AS x FROM demo_note WHERE demo_note_id = %s", (note["demo_note_id"],)) is None


def test_an_edit_on_the_website_is_never_overwritten(client, reader, player, book):
    grimoire_id = book["grimoire_id"]
    note = client.post(notes_path(grimoire_id), headers=player["headers"],
                       json={"note_type": "scribble", "content": "game"}).json()["note"]
    web = client.put(f"/api/demo/notes/{note['demo_note_id']}", headers=reader["cookie"], json={
        "grimoire_id": grimoire_id, "note_type": "scribble", "content": "website"})
    assert web.status_code == 200, web.text
    response = client.put(notes_path(grimoire_id, note["demo_note_id"]), headers=player["headers"],
                          json={"tag": "", "content": "game again", "if_updated_at": note["updated_at"]})
    assert response.status_code == 409 and response.json()["note"]["content"] == "website"
    assert sql_one("SELECT content FROM demo_note WHERE demo_note_id = %s", (note["demo_note_id"],))["content"] == "website"


def test_only_the_accounts_own_notes(client, player, book):
    other = game_key(account("betatester"))
    grimoire_id = book["grimoire_id"]
    theirs = client.post(notes_path(grimoire_id), headers=other["headers"],
                         json={"note_type": "scribble", "content": "theirs"}).json()["note"]
    mine = {row["demo_note_id"] for row in client.get(notes_path(grimoire_id), headers=player["headers"]).json()["notes"]}
    assert theirs["demo_note_id"] not in mine
    path = notes_path(grimoire_id, theirs["demo_note_id"])
    put = client.put(path, headers=player["headers"],
                     json={"tag": "", "content": "mine now", "if_updated_at": theirs["updated_at"]})
    delete = client.request("DELETE", path, headers=player["headers"], json={"if_updated_at": theirs["updated_at"]})
    for response in (put, delete):
        assert response.status_code == 404 and response.json()["code"] == "note_not_found"
    assert sql_one("SELECT content FROM demo_note WHERE demo_note_id = %s", (theirs["demo_note_id"],))["content"] == "theirs"


def test_notes_keep_the_web_demos_limits_and_need_its_access(client, player, stranger, book, illustrated):
    grimoire_id, ids = book["grimoire_id"], book["ids"]
    for body in (
        {"knowledge_id": ids["def-open"], "note_type": "attached", "tag": "t" * 121},
        {"knowledge_id": ids["def-open"], "note_type": "attached", "content": "c" * 50_001},
        {"knowledge_id": ids["def-open"], "note_type": "scribble"},
        {"note_type": "attached"},
        {"note_type": "scribble", "content": "nul \u0000"},
    ):
        response = client.post(notes_path(grimoire_id), headers=player["headers"], json=body)
        assert response.status_code == 422 and response.json()["code"] == "invalid_request", body
    within = client.post(notes_path(grimoire_id), headers=player["headers"], json={
        "knowledge_id": ids["def-open"], "note_type": "attached", "tag": "t" * 120, "content": "c" * 50_000})
    assert within.status_code == 201
    elsewhere = client.post(notes_path(grimoire_id), headers=player["headers"], json={
        "knowledge_id": illustrated["ids"]["def-open"], "note_type": "attached", "content": "wrong book"})
    assert elsewhere.status_code == 404 and elsewhere.json()["code"] == "object_not_found"
    refused = client.post(notes_path(grimoire_id), headers=stranger["headers"],
                          json={"note_type": "scribble", "content": "x"})
    assert refused.status_code == 403 and refused.json()["code"] == "demo_access_required"


# --- migration 017 -------------------------------------------------------------------------------

def game_catalogue(cur):
    cur.execute(
        """SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'book_game_read' ORDER BY ordinal_position"""
    )
    columns = [dict(row) for row in cur.fetchall()]
    cur.execute(
        """SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint
           WHERE conrelid = 'book_game_read'::regclass ORDER BY 1"""
    )
    return columns, [row["definition"] for row in cur.fetchall()]


def test_migration_017_brings_a_0_0_15_database_to_the_fresh_schema_and_can_run_again():
    with disposable_database("theumst_migration_017_test"):
        with database.transaction() as (_, cur):
            fresh = game_catalogue(cur)
            web = catalogue(cur)
            # The database as 0.0.15 left it, holding a demo book with its Web Demo read.
            cur.execute("DROP TABLE book_game_read")
            grimoire_id, language_id = _upsert_book(cur, {"source_key": "kept", "title": "Kept",
                                                          "metadata": {"demo": True}})
            sections = _upsert_sections(cur, grimoire_id, language_id, [{"source_key": "one", "section_number": "1"}])
            _upsert_objects(cur, grimoire_id=grimoire_id, language_id=language_id, sections=sections,
                            objects=[{"source_key": "a", "section_source_key": "one", "type": "theorem",
                                      "statement": "A"}])
            book_read.refresh(cur, grimoire_id)
        with pytest.raises(reviewed_migrations.MigrationSafetyError, match="book_game_read_v1"):
            reviewed_migrations.assert_database_schema_ready()

        first = reviewed_migrations.apply_reviewed_migrations(backup_sha256="0" * 64)
        actions = {entry["migration"]: entry["action"] for entry in first["migrations"]}
        assert actions.pop("book_game_read_v1") == "applied"
        assert set(actions.values()) == {"already_applied"}
        reviewed_migrations.assert_database_schema_ready()
        with database.transaction() as (_, cur):
            assert game_catalogue(cur) == fresh
            cur.execute("SELECT count(*) AS n FROM book_game_read")
            assert cur.fetchone()["n"] == 0  # 017 writes no rows
            source = next(path for migration, path in reviewed_migrations.validated_migration_sources()
                          if migration.key == "book_game_read_v1")
            cur.execute(source.read_text(encoding="utf-8"))  # it can run again
            assert game_catalogue(cur) == fresh

        again = reviewed_migrations.apply_reviewed_migrations(backup_sha256="0" * 64)
        assert {entry["action"] for entry in again["migrations"]} == {"already_applied"}
        out = io.StringIO()
        assert build_book_reads.run(out=out) == 0
        assert [line.split()[-3] for line in out.getvalue().splitlines()[1:-1]] == ["unchanged", "written"]
        assert sql_one("SELECT object_count FROM book_game_read WHERE grimoire_id = %s",
                       (grimoire_id,))["object_count"] == 1
    assert [(column["column_name"], column["data_type"]) for column in fresh[0]] == [
        (column["column_name"], column["data_type"]) for column in web[0]]
    assert "FOREIGN KEY (grimoire_id) REFERENCES grimoire(grimoire_id) ON DELETE CASCADE" in fresh[1]
