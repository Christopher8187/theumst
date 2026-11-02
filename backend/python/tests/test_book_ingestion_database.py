from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

from app.database import connect
from app.routers.demo import _object_images
from app.services.book_ingestion import (
    _image_link_type,
    _image_object_keys,
    _queue_embeddings,
    _upsert_book,
    _upsert_objects,
    _upsert_sections,
    _write_image_rows,
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


def _crystals(cursor, grimoire_id: int) -> dict[str, tuple[int, bool]]:
    cursor.execute(
        """
        SELECT k.source_key, k.knowledge_crystal_id, k.is_default_in_crystal
        FROM knowledge k JOIN section s ON s.section_id = k.section_id
        WHERE s.grimoire_id = %s
        """,
        (grimoire_id,),
    )
    return {row["source_key"]: (row["knowledge_crystal_id"], row["is_default_in_crystal"]) for row in cursor.fetchall()}


def test_crystal_source_keys_share_a_crystal_and_regroup_on_reimport_then_rollback():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            grimoire_id, language_id = _upsert_book(cursor, {
                "source_key": "__crystal_key_test__", "title": "Crystal key test", "language_id": 1,
            })
            sections = _upsert_sections(cursor, grimoire_id, language_id, [
                {"source_key": "section:1", "section_number": "1", "section_name": "One"},
            ])

            def upload(groups: dict[str, str | None]) -> dict[str, tuple[int, bool]]:
                _upsert_objects(
                    cursor, grimoire_id=grimoire_id, language_id=language_id, sections=sections,
                    objects=[
                        {"source_key": key, "section_source_key": "section:1", "type": "theorem",
                         "statement": key, "crystal_source_key": crystal,
                         "is_default_in_crystal": key == "object:1"}
                        for key, crystal in groups.items()
                    ],
                )
                return _crystals(cursor, grimoire_id)

            first = upload({"object:1": "__crystal__:a", "object:2": "__crystal__:a", "object:3": None})
            assert first["object:1"][0] == first["object:2"][0] != first["object:3"][0]
            assert first["object:1"][1] and not first["object:2"][1]

            # Republishing moves object:2 to its own keyed crystal and keeps object:3's unkeyed one.
            second = upload({"object:1": "__crystal__:a", "object:2": "__crystal__:b", "object:3": None})
            assert second["object:1"][0] == first["object:1"][0]
            assert second["object:2"][0] not in {first["object:1"][0], first["object:3"][0]}
            assert second["object:3"][0] == first["object:3"][0]

            with pytest.raises(HTTPException, match="crystal_source_key"):
                upload({"object:1": "  "})
    finally:
        connection.rollback()
        connection.close()


def test_figures_and_page_scans_reach_every_linked_object_and_relink_on_reimport_then_rollback():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            grimoire_id, language_id = _upsert_book(cursor, {
                "source_key": "__shared_image_test__", "title": "Shared image test", "language_id": 1,
            })
            sections = _upsert_sections(cursor, grimoire_id, language_id, [
                {"source_key": "section:1", "section_number": "1", "section_name": "One"},
            ])
            objects = _upsert_objects(
                cursor, grimoire_id=grimoire_id, language_id=language_id, sections=sections,
                objects=[
                    {"source_key": key, "section_source_key": "section:1", "type": "theorem", "statement": key}
                    for key in ("theorem", "support", "other")
                ],
            )

            def image(source_image_id: str, link_type: str, *keys: str, page: int | None = None) -> dict:
                entry = {
                    "source_image_id": source_image_id, "storage_key": f"books/test/{source_image_id}.png",
                    "url": f"/{source_image_id}.png", "section_id": sections["section:1"],
                    "semantic_context_name": source_image_id, "metadata": {"page": page} if page else {},
                    "object_source_key": keys[0], "object_source_keys": list(keys), "link_type": link_type,
                }
                ids = [objects[key]["knowledge_id"] for key in _image_object_keys(entry, objects)]
                kind = _image_link_type(entry)
                return dict(entry, knowledge_id=ids[0] if kind == "figure" else None, knowledge_ids=ids)

            def shown(key: str, link_type: str = "figure") -> list[str]:
                return [row["source_image_id"] for row in _object_images(cursor, objects[key]["knowledge_id"], link_type)]

            counts = _write_image_rows(cursor, [
                image("figure", "figure", "theorem", "support"),
                image("page-14", "page", "support", "theorem", page=14),
                image("page-13", "page", "theorem", page=13),
            ], grimoire_id)
            assert counts == {"figure": 2, "page": 3}
            assert (shown("theorem"), shown("support"), shown("other")) == (["figure"], ["figure"], [])
            assert (shown("theorem", "page"), shown("support", "page")) == (["page-13", "page-14"], ["page-14"])
            cursor.execute("SELECT knowledge_id FROM book_image WHERE source_image_id = 'page-14'")
            assert cursor.fetchone()["knowledge_id"] is None

            # Republishing relinks each image to the objects it lists now.
            counts = _write_image_rows(cursor, [image("figure", "figure", "theorem")], grimoire_id)
            assert counts == {"figure": 1, "page": 0}
            assert (shown("theorem"), shown("support")) == (["figure"], [])

            # A row stored before migration 012 has no links and still reaches its object as a figure.
            cursor.execute(
                """
                INSERT INTO book_image (grimoire_id, knowledge_id, source_image_id, storage_key, url)
                VALUES (%s, %s, 'legacy', 'books/test/legacy.png', '/legacy.png')
                """,
                (grimoire_id, objects["other"]["knowledge_id"]),
            )
            assert (shown("other"), shown("other", "page")) == (["legacy"], [])

            with pytest.raises(HTTPException, match="Unknown image object"):
                _image_object_keys({"object_source_keys": ["missing"]}, objects)
            with pytest.raises(HTTPException, match="link_type"):
                _image_link_type({"link_type": "cover"})
    finally:
        connection.rollback()
        connection.close()
