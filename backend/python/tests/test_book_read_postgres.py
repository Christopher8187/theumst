"""Opt-in real PostgreSQL checks of 0.0.15: the whole-book read, from ingestion to the route.

Set THEUMST_BOOK_READ_DB_TESTS=1 with LOCAL loopback database settings and a PostgreSQL account
that may create a database. The fixtures build UUID-named databases from schema.sql and drop them
afterwards; the configured database is untouched. Books arrive through the master-key Whole-book
upload and single-object submission, and are read through the Web Demo's routes with a session, so
the queries, the advisory lock, the savepoint and the transactions are PostgreSQL's own. No book
has embeddings or images, so nothing reaches Qdrant or storage.
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
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import RealDictCursor

from app import database, reviewed_migrations
from app.config import get_settings
from app.main import create_app
from app.security import hash_password, hash_secret
from app.services import book_read
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


def stored_row(grimoire_id):
    return sql_one("SELECT format, version, body_gzip, raw_bytes, object_count, built_at FROM book_read "
                   "WHERE grimoire_id = %s", (grimoire_id,))


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
    uploaded = {row["grimoire_id"]: row["version"] for row in sql_all("SELECT grimoire_id, version FROM book_read")}
    with database.transaction() as (_, cur):
        cur.execute("DELETE FROM book_read")
    books = [row["grimoire_id"] for row in sql_all("SELECT grimoire_id FROM grimoire ORDER BY grimoire_id")]

    first = io.StringIO()
    assert build_book_reads.run(out=first) == 0
    lines = first.getvalue().splitlines()
    assert lines[0] == "book_read format 1"
    assert [int(line.split()[1]) for line in lines[1:-1]] == books  # every book, hidden ones too, in id order
    assert all(line.split()[-3] == "written" for line in lines[1:-1])
    assert lines[-1].startswith(f"{len(books)} books: {len(books)} written, 0 unchanged, 0 failed; ")
    rows = {row["grimoire_id"]: row for row in sql_all("SELECT * FROM book_read")}
    assert set(rows) == set(books)
    for grimoire_id, version in uploaded.items():
        assert rows[grimoire_id]["version"] == version  # the same facts give ingestion's version

    second = io.StringIO()
    assert build_book_reads.run(out=second) == 0
    assert all(line.split()[-3] == "unchanged" for line in second.getvalue().splitlines()[1:-1])
    assert second.getvalue().splitlines()[-1].startswith(f"{len(books)} books: 0 written, {len(books)} unchanged, ")
    again = {row["grimoire_id"]: row for row in sql_all("SELECT * FROM book_read")}
    for grimoire_id, row in rows.items():
        assert again[grimoire_id]["built_at"] == row["built_at"]
        assert bytes(again[grimoire_id]["body_gzip"]) == bytes(row["body_gzip"])

    check = io.StringIO()
    assert build_book_reads.run(check=True, out=check) == 0
    assert all(line.split()[-3] == "current" for line in check.getvalue().splitlines()[1:-1])


def test_the_check_finds_stale_and_missing_books_and_writes_nothing(book):
    with database.transaction() as (_, cur):
        cur.execute("UPDATE book_read SET version = repeat('0', 64) WHERE grimoire_id = %s", (book["grimoire_id"],))
        cur.execute("DELETE FROM book_read WHERE grimoire_id = %s", (book["other"],))
    out = io.StringIO()
    assert build_book_reads.run([book["grimoire_id"], book["other"]], check=True, out=out) == 2
    words = {int(line.split()[1]): line.split()[-3] for line in out.getvalue().splitlines()[1:-1]}
    assert words == {book["grimoire_id"]: "stale", book["other"]: "missing"}
    assert stored_row(book["other"]) is None
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
