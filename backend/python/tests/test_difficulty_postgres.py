"""Opt-in real PostgreSQL checks of 0.0.14: the Web Demo's knowledge list and one object carry
difficulty and estimated_minutes, the object's source_metadata numbers of those names or null.

Set THEUMST_DIFFICULTY_DB_TESTS=1 with LOCAL loopback database settings and a PostgreSQL account that
may create a database. The fixture builds a UUID-named database from schema.sql and drops it afterwards;
the configured database is untouched. Requests go through the application with a betatester's session,
so jsonb_typeof, the casts and the ordering are PostgreSQL's own.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2.extras import RealDictCursor

from app import database
from app.config import get_settings
from app.main import create_app
from app.security import hash_password, hash_secret
from app.services.book_ingestion import _upsert_book, _upsert_objects, _upsert_sections


pytestmark = pytest.mark.skipif(
    os.getenv("THEUMST_DIFFICULTY_DB_TESTS") != "1", reason="Explicit isolated PostgreSQL acceptance only"
)

# Stored source_metadata beside its order, and the (difficulty, estimated_minutes) the routes answer.
CASES = [
    ("whole", {"difficulty": 40, "estimated_minutes": 12}, (40, 12)),
    ("fraction", {"difficulty": 37.5, "estimated_minutes": 0.05}, (37.5, 0.05)),
    ("zero", {"difficulty": 0, "estimated_minutes": -1}, (0, -1)),
    ("missing", {}, (None, None)),
    ("json-null", {"difficulty": None, "estimated_minutes": None}, (None, None)),
    ("text", {"difficulty": "40", "estimated_minutes": "12 minutes"}, (None, None)),
    ("object", {"difficulty": {"value": 40}, "estimated_minutes": [12]}, (None, None)),
    ("boolean", {"difficulty": True, "estimated_minutes": False}, (None, None)),
    ("one-of-two", {"difficulty": "hard", "estimated_minutes": 30}, (None, 30)),
]
# Whole source_metadata values that are not objects, written past the upload's own checks.
NOT_OBJECTS = [("array", "[40, 12]"), ("scalar", "40"), ("text-scalar", '"difficulty"')]

LIST_ROW_KEYS = [
    "knowledge_id", "section_id", "type", "source_key", "source_order", "name", "label", "completed",
    "difficulty", "estimated_minutes", "book_order_rank", "breadcrumbs",
]
DETAIL_KEYS = [
    "knowledge_id", "section_id", "type", "source_key", "source_order", "name", "label",
    "statement", "working", "working_summary", "completed", "difficulty", "estimated_minutes", "images", "pages",
]


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
def client():
    with disposable_database("theumst_difficulty_test"):
        yield TestClient(create_app(initialize_services=False))


@pytest.fixture(scope="module")
def book(client):
    """A Web Demo book holding one object per case, in that order, and a betatester's session."""
    objects = [
        {"source_key": key, "section_source_key": "one", "type": "theorem", "statement": f"Statement {key}",
         "label": f"Theorem {position}", "source_metadata": {"order": [position], **metadata}}
        for position, (key, metadata, _) in enumerate(CASES, 1)
    ] + [
        {"source_key": key, "section_source_key": "one", "type": "theorem", "statement": f"Statement {key}",
         "label": key, "source_metadata": {"order": [len(CASES) + position]}}
        for position, (key, _) in enumerate(NOT_OBJECTS, 1)
    ]
    with database.transaction() as (_, cur):
        grimoire_id, language_id = _upsert_book(
            cur, {"source_key": f"book-{uuid4().hex[:8]}", "title": "Algebra", "metadata": {"demo": True}},
        )
        sections = _upsert_sections(cur, grimoire_id, language_id, [
            {"source_key": "one", "section_number": "1", "section_name": "Groups"},
        ])
        made = _upsert_objects(cur, grimoire_id=grimoire_id, language_id=language_id, sections=sections,
                               objects=objects)
        ids = {key: row["knowledge_id"] for key, row in made.items()}
        for key, stored in NOT_OBJECTS:
            cur.execute("UPDATE knowledge SET source_metadata = %s::jsonb WHERE knowledge_id = %s", (stored, ids[key]))
        name = f"betatester_{uuid4().hex[:10]}"
        cur.execute(
            """INSERT INTO "user" (username, email, password_hash, authority_id, email_verified_at)
               SELECT %s, %s, %s, authority_id, now() FROM authority WHERE name = 'betatester' RETURNING user_id""",
            (name, f"{name}@example.invalid", hash_password("unused-passphrase")),
        )
        user_id = cur.fetchone()["user_id"]
        cur.execute("INSERT INTO demo_knowledge_progress (user_id, knowledge_id, completed) VALUES (%s, %s, true)",
                    (user_id, ids["whole"]))
        token = uuid4().hex + uuid4().hex
        cur.execute(
            "INSERT INTO web_session (user_id, token_hash, expires_at) VALUES (%s, %s, now() + interval '1 day')",
            (user_id, hash_secret(token)),
        )
    return {"grimoire_id": grimoire_id, "ids": ids, "headers": {"Cookie": f"{get_settings().cookie_name}={token}"}}


def expected():
    return [(key, answer) for key, _, answer in CASES] + [(key, (None, None)) for key, _ in NOT_OBJECTS]


def listed(client, book):
    response = client.get(f"/api/demo/grimoires/{book['grimoire_id']}/knowledge", headers=book["headers"])
    assert response.status_code == 200, response.text
    return response.json()["knowledge"]


def test_the_list_gives_each_objects_numbers_or_null(client, book):
    rows = listed(client, book)
    assert [row["knowledge_id"] for row in rows] == [book["ids"][key] for key, _ in expected()]
    for row, (key, answer) in zip(rows, expected()):
        assert (row["difficulty"], row["estimated_minutes"]) == answer, key
        for value, wanted in zip((row["difficulty"], row["estimated_minutes"]), answer):
            assert type(value) is type(wanted), key  # 40 stays a whole number, true and "40" stay out


def test_one_object_gives_its_numbers_or_null(client, book):
    for key, answer in expected():
        response = client.get(f"/api/demo/grimoires/{book['grimoire_id']}/knowledge/{book['ids'][key]}",
                              headers=book["headers"])
        assert response.status_code == 200, response.text
        knowledge = response.json()["knowledge"]
        assert (knowledge["difficulty"], knowledge["estimated_minutes"]) == answer, key
        assert [type(value) for value in (knowledge["difficulty"], knowledge["estimated_minutes"])] == \
            [type(value) for value in answer], key


def test_every_other_field_and_the_order_stay_as_they_were(client, book):
    rows = listed(client, book)
    assert all(list(row) == LIST_ROW_KEYS for row in rows)
    first = rows[0]
    section_id = first["section_id"]
    assert first == {
        "knowledge_id": book["ids"]["whole"], "section_id": section_id, "type": "theorem", "source_key": "whole",
        "source_order": [1], "name": None, "label": "Theorem 1", "completed": True,
        "difficulty": 40, "estimated_minutes": 12, "book_order_rank": 1,
        "breadcrumbs": [{"section_id": section_id, "number": "1", "name": "Groups"}],
    }
    assert [row["book_order_rank"] for row in rows] == list(range(1, len(rows) + 1))
    assert [row["completed"] for row in rows] == [True] + [False] * (len(rows) - 1)
    # A source_metadata that is not an object loses its order too, as before, and sorts after the rest.
    assert [row["source_order"] for row in rows[-len(NOT_OBJECTS):]] == [None] * len(NOT_OBJECTS)

    response = client.get(f"/api/demo/grimoires/{book['grimoire_id']}/knowledge/{book['ids']['whole']}",
                          headers=book["headers"])
    knowledge = response.json()["knowledge"]
    assert list(knowledge) == DETAIL_KEYS
    assert knowledge == {
        "knowledge_id": book["ids"]["whole"], "section_id": section_id, "type": "theorem",
        "source_key": "whole", "source_order": [1], "name": None, "label": "Theorem 1",
        "statement": "Statement whole", "working": "", "working_summary": None, "completed": True,
        "difficulty": 40, "estimated_minutes": 12, "images": [], "pages": [],
    }
