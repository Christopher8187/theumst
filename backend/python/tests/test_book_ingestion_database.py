from __future__ import annotations

import os

import pytest

from app.database import connect
from app.services.book_ingestion import (
    _queue_embeddings,
    _upsert_book,
    _upsert_objects,
    _upsert_sections,
)


pytestmark = pytest.mark.skipif(
    os.getenv("THEUMST_DATABASE_INTEGRATION") != "1",
    reason="set THEUMST_DATABASE_INTEGRATION=1 against a disposable or local deployment",
)


def test_batched_book_rows_and_embeddings_round_trip_then_rollback():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            grimoire_id, language_id = _upsert_book(cursor, {
                "source_key": "__batch_ingestion_test__",
                "title": "Batch ingestion test",
                "language_id": 1,
            })
            sections = _upsert_sections(cursor, grimoire_id, language_id, [
                {"source_key": "section:1", "section_number": "1", "section_name": "One"},
                # A child may legitimately repeat its parent's visible number;
                # parent identity is part of the legacy uniqueness constraint.
                {"source_key": "section:2", "section_number": "1", "section_name": "Two", "parent_source_key": "section:1"},
            ])
            objects = _upsert_objects(
                cursor,
                grimoire_id=grimoire_id,
                language_id=language_id,
                sections=sections,
                objects=[
                    {"source_key": "object:1", "section_source_key": "section:1", "type": "definition", "statement": "One"},
                    {"source_key": "object:2", "section_source_key": "section:2", "type": "context", "statement": "Two"},
                ],
            )
            points = _queue_embeddings(cursor, objects, [
                {
                    "local_object_id": source_key,
                    "projection_type": "statement",
                    "direction": "self",
                    "embedding_text": source_key,
                    "vector": [0.1, 0.2, 0.3],
                    "model": {
                        "provider": "test",
                        "model_name": "rollback-model",
                        "model_revision": "1",
                        "distance_metric": "cosine",
                        "qdrant_collection": "__batch_ingestion_test__",
                    },
                }
                for source_key in objects
            ], {})
            assert len(sections) == 2
            assert len(objects) == 2
            assert len(points) == 2
            assert all(len(point["vector"]) == 3 for point in points)
    finally:
        connection.rollback()
        connection.close()
