"""The Web Demo's knowledge list and one object carry difficulty and estimated_minutes (0.0.14).

A stand-in cursor answers each query by its text. These tests check the two routes' SQL and what the
routes pass on; test_difficulty_postgres.py checks what PostgreSQL itself gives for a number, a missing
key and every other kind of stored value.
"""
from __future__ import annotations

import re
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import demo


GUARDED = (
    "CASE WHEN jsonb_typeof(k.source_metadata->'difficulty') = 'number' "
    "THEN k.source_metadata->'difficulty' END AS difficulty, "
    "CASE WHEN jsonb_typeof(k.source_metadata->'estimated_minutes') = 'number' "
    "THEN k.source_metadata->'estimated_minutes' END AS estimated_minutes"
)
# The columns each route selected before 0.0.14, in their order.
LIST_COLUMNS_BEFORE = (
    "k.knowledge_id, k.section_id, k.type, k.source_key, "
    "k.source_metadata->'order' AS source_order, "
    "k.name, COALESCE(NULLIF(btrim(k.name), ''), lk.label) AS label, "
    "COALESCE(p.completed, false) AS completed"
)
DETAIL_COLUMNS_BEFORE = (
    "k.knowledge_id, k.section_id, k.type, k.source_key, "
    "k.source_metadata->'order' AS source_order, "
    "k.name, COALESCE(NULLIF(btrim(k.name), ''), lk.label) AS label, lk.statement, lk.working, lk.working_summary, "
    "COALESCE(p.completed, false) AS completed"
)

LIST_ROW_KEYS = [
    "knowledge_id", "section_id", "type", "source_key", "source_order", "name", "label", "completed",
    "difficulty", "estimated_minutes", "book_order_rank", "breadcrumbs",
]
DETAIL_KEYS = [
    "knowledge_id", "section_id", "type", "source_key", "source_order", "name", "label",
    "statement", "working", "working_summary", "completed", "difficulty", "estimated_minutes", "images", "pages",
]


def knowledge_row(knowledge_id, difficulty, minutes, **extra):
    return {
        "knowledge_id": knowledge_id, "section_id": 3, "type": "theorem", "source_key": f"t{knowledge_id}",
        "source_order": [knowledge_id], "name": None, "label": f"Theorem {knowledge_id}", **extra,
        "completed": False, "difficulty": difficulty, "estimated_minutes": minutes,
    }


ROWS = [knowledge_row(11, 40, 12), knowledge_row(12, 37.5, 0.05), knowledge_row(13, None, None)]


class Cursor:
    """Answers the two routes' queries by their text and keeps every query it was given."""

    def __init__(self):
        self.queries: list[str] = []
        self.answer = None

    def execute(self, query, parameters=None):
        text = " ".join(query.split())
        self.queries.append(text)
        if "FROM grimoire g JOIN language_grimoire" in text:
            self.answer = [{"grimoire_id": 7, "title": "Algebra"}]
        elif "FROM section s" in text and "FROM knowledge k" not in text:
            self.answer = [{"section_id": 3, "parent_section": None, "section_number": "1", "section_name": "Groups"}]
        elif "FROM knowledge k" in text and "lk.statement" in text:
            self.answer = [knowledge_row(11, 40, 12, statement="S", working="W", working_summary=None)]
        elif "FROM knowledge k" in text:
            self.answer = [dict(row) for row in ROWS]
        else:  # user_grimoire, relation counts, study state, images
            self.answer = []

    def fetchone(self):
        return self.answer[0] if self.answer else None

    def fetchall(self):
        return self.answer


@pytest.fixture
def cursor(monkeypatch):
    cursor = Cursor()

    @contextmanager
    def transaction():
        yield object(), cursor

    monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 5})
    monkeypatch.setattr(demo, "transaction", transaction)
    return cursor


@pytest.fixture
def client():
    application = FastAPI()
    application.include_router(demo.router)
    return TestClient(application)


def selected_columns(query):
    return re.match(r"SELECT (.*) FROM knowledge k ", query).group(1)


def knowledge_query(cursor):
    return next(query for query in cursor.queries if query.startswith("SELECT k.knowledge_id"))


def test_the_list_selects_both_fields_after_its_old_columns_and_passes_them_on(client, cursor):
    response = client.get("/api/demo/grimoires/7/knowledge")
    assert response.status_code == 200, response.text
    assert selected_columns(knowledge_query(cursor)) == f"{LIST_COLUMNS_BEFORE}, {GUARDED}"
    rows = response.json()["knowledge"]
    assert [list(row) for row in rows] == [LIST_ROW_KEYS] * 3
    assert [(row["difficulty"], row["estimated_minutes"]) for row in rows] == [(40, 12), (37.5, 0.05), (None, None)]
    assert [row["book_order_rank"] for row in rows] == [1, 2, 3]
    assert rows[0]["breadcrumbs"] == [{"section_id": 3, "number": "1", "name": "Groups"}]
    assert set(response.json()) == {
        "book", "sections", "knowledge", "relation_counts", "current_knowledge_id", "questions_knowledge_id",
    }


def test_one_object_selects_both_fields_after_its_old_columns_and_passes_them_on(client, cursor):
    response = client.get("/api/demo/grimoires/7/knowledge/11")
    assert response.status_code == 200, response.text
    assert selected_columns(knowledge_query(cursor)) == f"{DETAIL_COLUMNS_BEFORE}, {GUARDED}"
    assert list(response.json()) == ["knowledge"]
    knowledge = response.json()["knowledge"]
    assert list(knowledge) == DETAIL_KEYS
    assert (knowledge["difficulty"], knowledge["estimated_minutes"]) == (40, 12)


def test_the_row_order_is_untouched(client, cursor):
    client.get("/api/demo/grimoires/7/knowledge")
    assert knowledge_query(cursor).endswith(
        "WHERE s.grimoire_id = %s AND k.is_active "
        "ORDER BY COALESCE((k.source_metadata->>'demo_order')::int, 2147483647), "
        "k.source_metadata->'order' NULLS LAST, k.knowledge_id"
    )
