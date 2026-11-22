"""Mocked PostgreSQL/Qdrant checks for reader-facing semantic discovery.

These tests exercise application scoring and query orchestration. They do not
establish behavior of a live PostgreSQL or Qdrant service.

Since 0.0.19 find_neighbors' reach is bounded: PostgreSQL reads the source's own
projections, Qdrant ranks with the hidden books and the source left out by its
filter, and PostgreSQL then reads only the hits' rows.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi import HTTPException

from app.routers import demo
from app.services import discovery

HIDDEN_BOOK = 99


class ScriptedCursor:
    def __init__(self, *, one=None, all_rows=None):
        self.one = list(one or [])
        self.all_rows = list(all_rows or [])
        self.executions = []

    def execute(self, statement, values=None):
        self.executions.append((statement, values))

    def fetchone(self):
        return self.one.pop(0)

    def fetchall(self):
        return self.all_rows.pop(0)


def scripted_transactions(monkeypatch, *cursors):
    pending = list(cursors)

    @contextmanager
    def fake_transaction():
        yield None, pending.pop(0)

    monkeypatch.setattr(discovery, "transaction", fake_transaction)
    return pending


def projection(
    knowledge_id,
    projection_type,
    embedding_id,
    *,
    grimoire_id=10,
    has_workings=True,
):
    return {
        "embedding_id": embedding_id,
        "embedding_model_id": 7,
        "projection_type": projection_type,
        "language_id": 1,
        "direction": "self",
        "knowledge_id": knowledge_id,
        "grimoire_id": grimoire_id,
        "label": f"Knowledge {knowledge_id}",
        "statement": f"Statement {knowledge_id}",
        "book_title": f"Book {grimoire_id}",
        "has_workings": has_workings,
        "qdrant_collection": "reader-vectors",
        "vector_size": 8,
        "distance_metric": "cosine",
    }


def source_row(*, has_workings=True):
    return {
        "knowledge_id": 1,
        "grimoire_id": 10,
        "language_id": 1,
        "has_workings": has_workings,
    }


HIDDEN = [{"grimoire_id": HIDDEN_BOOK}]


def first_cursor(source_rows, *, has_workings=True):
    """The first transaction: the source, its own projections, and the hidden books."""
    return ScriptedCursor(one=[source_row(has_workings=has_workings)], all_rows=[source_rows, HIDDEN])


def hit(point_id, knowledge_id, score):
    return {"id": point_id, "score": score, "payload": {"knowledge_id": knowledge_id}}


def test_combined_score_normalizes_equal_average_and_signed_penalty():
    assert discovery.combined_score(0.5, -0.5, True, True) == pytest.approx(0.5)
    assert discovery.combined_score(-0.5, None, True, False) == pytest.approx(0.2)
    assert discovery.combined_score(-0.5, None, False, False) == pytest.approx(0.25)

    with pytest.raises(ValueError, match="combined projection"):
        discovery.combined_score(0.5, None, True, True)
    with pytest.raises(ValueError, match="cosine statement"):
        discovery.combined_score(float("nan"), None, False, False)


def test_missing_source_projection_is_a_processing_error_before_qdrant(monkeypatch):
    cursor = first_cursor([projection(1, "statement", "source-statement")])
    scripted_transactions(monkeypatch, cursor)
    monkeypatch.setattr(
        discovery.qdrant_service,
        "query_raw",
        lambda **_: pytest.fail("Qdrant must not run with an incomplete source pair"),
    )

    with pytest.raises(HTTPException) as raised:
        discovery.find_neighbors(1, 10)

    assert raised.value.status_code == 409
    assert "Combined projection" in raised.value.detail


def test_the_source_reads_only_its_own_projections_and_qdrant_filters_hidden_books(monkeypatch):
    source = [projection(1, "statement", "source-statement", has_workings=False)]
    cursor = first_cursor(source, has_workings=False)
    hits_cursor = ScriptedCursor(all_rows=[[*source, projection(3, "statement", "three", has_workings=False)]])
    scripted_transactions(monkeypatch, cursor, hits_cursor)
    bodies = []

    def query_raw(*, collection, body):
        bodies.append((collection, body))
        return [hit("three", 3, 0.5)]

    monkeypatch.setattr(discovery.qdrant_service, "query_raw", query_raw)

    response = discovery.find_neighbors(1, 10)

    assert [row["knowledge_id"] for row in response["results"]] == [3]
    projections_sql, projections_values = cursor.executions[1]
    assert "sp.knowledge_id=ANY(%s)" in projections_sql
    assert projections_values == ([1], 1)
    collection, body = bodies[0]
    assert collection == "reader-vectors" and body["query"] == "source-statement" and body["limit"] == 15
    assert {"key": "projection_type", "match": {"value": "statement"}} in body["filter"]["must"]
    assert body["filter"]["must_not"] == [
        {"key": "knowledge_id", "match": {"value": 1}},
        {"key": "grimoire_id", "match": {"any": [HIDDEN_BOOK]}},
    ]
    hits_sql, hits_values = hits_cursor.executions[0]
    assert "g.source_metadata->>'demo'='true'" in hits_sql
    assert hits_values == ([1, 3], 1)


def test_missing_target_projection_is_counted_while_no_workings_is_retained(monkeypatch):
    source = [projection(1, "statement", "source-statement"), projection(1, "combined", "source-combined")]
    cursor = first_cursor(source)
    hits_cursor = ScriptedCursor(all_rows=[[
        *source,
        projection(2, "statement", "broken-statement", grimoire_id=20, has_workings=True),
        projection(3, "statement", "no-workings-statement", grimoire_id=30, has_workings=False),
    ]])
    scripted_transactions(monkeypatch, cursor, hits_cursor)

    def query_raw(*, collection, body):
        if body["query"] == "source-statement":
            return [hit("no-workings-statement", 3, 0.5), hit("broken-statement", 2, 0.45)]
        assert body["query"] == "source-combined"
        return []

    monkeypatch.setattr(discovery.qdrant_service, "query_raw", query_raw)
    monkeypatch.setattr(discovery.qdrant_service, "query_candidates",
                        lambda **_: pytest.fail("no candidate is missing a score"))

    response = discovery.find_neighbors(1, 10)

    assert response["processing_faults"] == 1
    assert [row["knowledge_id"] for row in response["results"]] == [3]
    assert response["results"][0]["similarity_score"] == pytest.approx(0.6)


def test_top_k_union_rescores_counterparts_then_ranks_cross_book_results(monkeypatch):
    source = [projection(1, "statement", "source-statement"), projection(1, "combined", "source-combined")]
    cursor = first_cursor(source)
    hits_cursor = ScriptedCursor(all_rows=[[
        *source,
        projection(2, "statement", "two-statement", grimoire_id=20),
        projection(2, "combined", "two-combined", grimoire_id=20),
        projection(3, "statement", "three-statement", grimoire_id=30),
        projection(3, "combined", "three-combined", grimoire_id=30),
    ]])
    scripted_transactions(monkeypatch, cursor, hits_cursor)

    def query_raw(*, collection, body):
        return {
            "source-statement": [hit("two-statement", 2, 0.8)],
            "source-combined": [hit("three-combined", 3, 0.9)],
        }[body["query"]]

    calls = []

    def query_candidates(*, point_id, candidate_ids, limit, **_):
        calls.append((point_id, tuple(candidate_ids), limit))
        scripted = {
            ("source-statement", ("three-statement",), 1): [{"id": "three-statement", "score": 0.7}],
            ("source-combined", ("two-combined",), 1): [{"id": "two-combined", "score": 0.6}],
        }
        return scripted[(point_id, tuple(candidate_ids), limit)]

    monkeypatch.setattr(discovery.qdrant_service, "query_raw", query_raw)
    monkeypatch.setattr(discovery.qdrant_service, "query_candidates", query_candidates)

    response = discovery.find_neighbors(1, 1)

    assert response["scope"] == "available_books"
    assert response["requested_k"] == 1
    assert [row["knowledge_id"] for row in response["results"]] == [3]
    assert response["results"][0]["grimoire_id"] == 30
    assert response["results"][0]["similarity_score"] == pytest.approx(0.9)
    assert sorted(calls) == [
        ("source-combined", ("two-combined",), 1),
        ("source-statement", ("three-statement",), 1),
    ]
    assert "s.grimoire_id=%s" not in hits_cursor.executions[0][0]


def test_a_point_not_owned_by_its_payloads_object_is_not_scored(monkeypatch):
    source = [projection(1, "statement", "source-statement", has_workings=False)]
    cursor = first_cursor(source, has_workings=False)
    hits_cursor = ScriptedCursor(all_rows=[[*source, projection(3, "statement", "three", has_workings=False)]])
    scripted_transactions(monkeypatch, cursor, hits_cursor)
    monkeypatch.setattr(discovery.qdrant_service, "query_raw", lambda **_: [hit("forged", 3, 0.99)])
    monkeypatch.setattr(discovery.qdrant_service, "query_candidates", lambda **_: [])

    assert discovery.find_neighbors(1, 10)["results"] == []


def test_hidden_source_stops_before_qdrant(monkeypatch):
    cursor = ScriptedCursor(one=[None])
    scripted_transactions(monkeypatch, cursor)
    monkeypatch.setattr(
        discovery.qdrant_service,
        "query_raw",
        lambda **_: pytest.fail("Qdrant must not run for a hidden source"),
    )

    with pytest.raises(HTTPException) as raised:
        discovery.find_neighbors(1, 10)

    assert raised.value.status_code == 404
    assert "g.source_metadata->>'demo'='true'" in cursor.executions[0][0]


@pytest.mark.parametrize(
    ("visible_rows", "expected_status", "expected_ids"),
    [
        ([projection(2, "statement", "two-statement", grimoire_id=20, has_workings=False)], 404, None),
        ([projection(1, "statement", "source-statement", has_workings=False)], None, []),
    ],
)
def test_visibility_is_rechecked_after_vector_query(
    monkeypatch, visible_rows, expected_status, expected_ids
):
    cursor = first_cursor([projection(1, "statement", "source-statement", has_workings=False)],
                          has_workings=False)
    visibility = ScriptedCursor(all_rows=[visible_rows])
    scripted_transactions(monkeypatch, cursor, visibility)
    monkeypatch.setattr(
        discovery.qdrant_service,
        "query_raw",
        lambda **_: [hit("two-statement", 2, 0.75)],
    )

    if expected_status is not None:
        with pytest.raises(HTTPException) as raised:
            discovery.find_neighbors(1, 10)
        assert raised.value.status_code == expected_status
    else:
        response = discovery.find_neighbors(1, 10)
        assert [row["knowledge_id"] for row in response["results"]] == expected_ids

    visibility_sql, visibility_values = visibility.executions[0]
    assert "sp.knowledge_id=ANY(%s)" in visibility_sql
    assert "g.source_metadata->>'demo'='true'" in visibility_sql
    assert visibility_values == ([1, 2], 1)


def test_vector_store_failure_is_503(monkeypatch):
    cursor = first_cursor([projection(1, "statement", "source-statement", has_workings=False)],
                          has_workings=False)
    scripted_transactions(monkeypatch, cursor)

    def down(**_):
        raise HTTPException(502, "Qdrant down")

    monkeypatch.setattr(discovery.qdrant_service, "query_raw", down)
    with pytest.raises(HTTPException) as raised:
        discovery.find_neighbors(1, 10)
    assert raised.value.status_code == 503


def test_neighbors_rejects_unauthorized_request_before_database(monkeypatch):
    monkeypatch.setattr(
        demo,
        "_demo_user",
        lambda _request: (_ for _ in ()).throw(HTTPException(403, "Demo access required")),
    )
    monkeypatch.setattr(
        discovery,
        "find_neighbors",
        lambda *_: pytest.fail("Discovery must not run before authorization"),
    )

    with pytest.raises(HTTPException) as raised:
        demo.neighbors(1, object(), k=10)

    assert raised.value.status_code == 403
