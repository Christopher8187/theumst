from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from collections import defaultdict
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException, UploadFile

from ..database import transaction
from . import storage
from .qdrant import qdrant_service

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 20_000
MAX_OBJECTS = 500_000
MAX_EMBEDDINGS = 1_500_000


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _safe_archive(data: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    if not data:
        raise HTTPException(status_code=422, detail="The ingestion archive is empty")
    if len(data) > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="The ingestion archive is too large")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid ZIP archive") from exc

    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_ENTRIES:
        raise HTTPException(status_code=413, detail="The archive contains too many entries")
    total = 0
    files: dict[str, bytes] = {}
    for member in members:
        name = member.filename.replace("\\", "/").lstrip("/")
        parts = [part for part in name.split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            raise HTTPException(status_code=422, detail=f"Unsafe archive member: {member.filename!r}")
        if member.is_dir():
            continue
        total += int(member.file_size)
        if total > MAX_UNCOMPRESSED_BYTES:
            raise HTTPException(status_code=413, detail="The uncompressed archive is too large")
        files["/".join(parts)] = archive.read(member)
    try:
        manifest = json.loads(files.pop("manifest.json").decode("utf-8"))
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="manifest.json is missing") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="manifest.json is invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise HTTPException(status_code=422, detail="Unsupported ingestion manifest")
    return manifest, files


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail=f"{name} is required")
    return text


def _validate_manifest(manifest: dict[str, Any]) -> None:
    book = manifest.get("book")
    sections = manifest.get("sections")
    objects = manifest.get("objects")
    embeddings = manifest.get("embeddings")
    images = manifest.get("images")
    if not isinstance(book, dict):
        raise HTTPException(status_code=422, detail="book must be an object")
    _required_text(book.get("source_key"), "book.source_key")
    if not isinstance(sections, list) or not isinstance(objects, list):
        raise HTTPException(status_code=422, detail="sections and objects must be arrays")
    if not isinstance(embeddings, list) or not isinstance(images, list):
        raise HTTPException(status_code=422, detail="embeddings and images must be arrays")
    if len(objects) > MAX_OBJECTS or len(embeddings) > MAX_EMBEDDINGS:
        raise HTTPException(status_code=413, detail="The manifest contains too many records")


def _upsert_book(cur, book: dict[str, Any]) -> tuple[int, int]:
    source_key = _required_text(book.get("source_key"), "book.source_key")
    language_id = int(book.get("language_id") or 1)
    cur.execute("SELECT language_id FROM language WHERE language_id = %s", (language_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=422, detail=f"Unknown language_id {language_id}")
    cur.execute(
        """
        INSERT INTO grimoire (source_key, isbn, publish_date, version, source_metadata)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (source_key) WHERE source_key IS NOT NULL DO UPDATE SET
            isbn = EXCLUDED.isbn,
            publish_date = EXCLUDED.publish_date,
            version = EXCLUDED.version,
            source_metadata = EXCLUDED.source_metadata
        RETURNING grimoire_id
        """,
        (source_key, book.get("isbn"), book.get("publish_date"), book.get("version"), _json(book.get("metadata") or {})),
    )
    grimoire_id = int(cur.fetchone()["grimoire_id"])
    cur.execute(
        """
        INSERT INTO language_grimoire (
            language_id, grimoire_id, title, is_original_language, publisher
        ) VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (language_id, grimoire_id) DO UPDATE SET
            title = EXCLUDED.title,
            is_original_language = EXCLUDED.is_original_language,
            publisher = EXCLUDED.publisher
        """,
        (
            language_id,
            grimoire_id,
            _required_text(book.get("title") or book.get("book_name") or source_key, "book.title"),
            bool(book.get("is_original_language", True)),
            str(book.get("publisher") or "Unknown"),
        ),
    )
    return grimoire_id, language_id


def _upsert_sections(cur, grimoire_id: int, language_id: int, sections: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for section in sections:
        source_key = _required_text(section.get("source_key"), "section.source_key")
        cur.execute(
            """
            INSERT INTO section (parent_section, grimoire_id, section_number, source_key, source_metadata)
            VALUES (NULL, %s, %s, %s, %s::jsonb)
            ON CONFLICT (grimoire_id, source_key) WHERE source_key IS NOT NULL DO UPDATE SET
                section_number = EXCLUDED.section_number,
                source_metadata = EXCLUDED.source_metadata
            RETURNING section_id
            """,
            (
                grimoire_id,
                _required_text(section.get("section_number") or source_key, "section.section_number"),
                source_key,
                _json(section.get("metadata") or {}),
            ),
        )
        section_id = int(cur.fetchone()["section_id"])
        result[source_key] = section_id
        cur.execute(
            """
            INSERT INTO language_section (
                language_id, section_id, section_name, section_head, section_tail
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (language_id, section_id) DO UPDATE SET
                section_name = EXCLUDED.section_name,
                section_head = EXCLUDED.section_head,
                section_tail = EXCLUDED.section_tail
            """,
            (
                language_id,
                section_id,
                section.get("section_name"),
                section.get("section_head"),
                section.get("section_tail"),
            ),
        )
    for section in sections:
        parent_key = section.get("parent_source_key")
        if not parent_key:
            continue
        source_key = str(section["source_key"])
        if parent_key not in result:
            raise HTTPException(status_code=422, detail=f"Unknown parent section {parent_key!r}")
        cur.execute(
            "UPDATE section SET parent_section = %s WHERE section_id = %s",
            (result[parent_key], result[source_key]),
        )
    return result


def _upsert_objects(
    cur,
    *,
    grimoire_id: int,
    language_id: int,
    sections: dict[str, int],
    objects: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for obj in objects:
        source_key = _required_text(obj.get("source_key"), "object.source_key")
        section_key = _required_text(obj.get("section_source_key"), "object.section_source_key")
        section_id = sections.get(section_key)
        if section_id is None:
            raise HTTPException(status_code=422, detail=f"Unknown section {section_key!r}")
        cur.execute(
            "SELECT knowledge_id, knowledge_crystal_id FROM knowledge WHERE section_id = %s AND source_key = %s",
            (section_id, source_key),
        )
        existing = cur.fetchone()
        if existing:
            knowledge_id = int(existing["knowledge_id"])
            cur.execute(
                """
                UPDATE knowledge SET type = %s, is_default_in_crystal = %s,
                    source_metadata = %s::jsonb, is_active = true
                WHERE knowledge_id = %s
                """,
                (str(obj.get("type") or "just a statement"), bool(obj.get("is_default_in_crystal", True)), _json(obj.get("source_metadata") or {}), knowledge_id),
            )
        else:
            cur.execute(
                "INSERT INTO knowledge_crystal (likes) VALUES (%s) RETURNING knowledge_crystal_id",
                (max(0, int(obj.get("likes") or 0)),),
            )
            crystal_id = int(cur.fetchone()["knowledge_crystal_id"])
            cur.execute(
                """
                INSERT INTO knowledge (
                    section_id, knowledge_crystal_id, type, is_default_in_crystal,
                    source_key, source_metadata, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, true)
                RETURNING knowledge_id
                """,
                (section_id, crystal_id, str(obj.get("type") or "just a statement"), bool(obj.get("is_default_in_crystal", True)), source_key, _json(obj.get("source_metadata") or {})),
            )
            knowledge_id = int(cur.fetchone()["knowledge_id"])
        cur.execute(
            """
            INSERT INTO language_knowledge (
                language_id, knowledge_id, working, statement, label,
                working_summary, ref_id, labelled_references,
                object_reference_labels, loose_references_guessed_objects,
                source_metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb
            )
            ON CONFLICT (language_id, knowledge_id) DO UPDATE SET
                working = EXCLUDED.working,
                statement = EXCLUDED.statement,
                label = EXCLUDED.label,
                working_summary = EXCLUDED.working_summary,
                ref_id = EXCLUDED.ref_id,
                labelled_references = EXCLUDED.labelled_references,
                object_reference_labels = EXCLUDED.object_reference_labels,
                loose_references_guessed_objects = EXCLUDED.loose_references_guessed_objects,
                source_metadata = EXCLUDED.source_metadata
            """,
            (
                language_id,
                knowledge_id,
                str(obj.get("working") or ""),
                _required_text(obj.get("statement"), "object.statement"),
                obj.get("label"),
                obj.get("working_summary"),
                obj.get("ref_id"),
                _json(obj.get("labelled_references") or []),
                _json(obj.get("object_reference_labels") or []),
                _json(obj.get("loose_references_guessed_objects") or []),
                _json(obj.get("language_metadata") or {}),
            ),
        )
        result[source_key] = {
            "knowledge_id": knowledge_id,
            "section_id": section_id,
            "grimoire_id": grimoire_id,
            "language_id": language_id,
            "working_type": str(obj.get("type") or "just a statement"),
        }
    return result



def _deactivate_book_state(cur, grimoire_id: int) -> None:
    cur.execute(
        """
        UPDATE semantic_projection sp SET is_active = false, updated_at = now()
        FROM knowledge k
        JOIN section s ON s.section_id = k.section_id
        WHERE sp.knowledge_id = k.knowledge_id
          AND s.grimoire_id = %s
          AND k.source_key IS NOT NULL
        """,
        (grimoire_id,),
    )
    cur.execute(
        """
        UPDATE knowledge k SET is_active = false
        FROM section s
        WHERE s.section_id = k.section_id
          AND s.grimoire_id = %s
          AND k.source_key IS NOT NULL
        """,
        (grimoire_id,),
    )
    cur.execute(
        "UPDATE book_image SET is_active = false, updated_at = now() WHERE grimoire_id = %s",
        (grimoire_id,),
    )


def _stale_embedding_points(cur, grimoire_id: int) -> list[dict[str, str]]:
    cur.execute(
        """
        SELECT e.embedding_id::text AS embedding_id, em.qdrant_collection
        FROM embedding e
        JOIN semantic_projection sp ON sp.semantic_projection_id = e.semantic_projection_id
        JOIN embedding_model em ON em.embedding_model_id = e.embedding_model_id
        JOIN knowledge k ON k.knowledge_id = sp.knowledge_id
        JOIN section s ON s.section_id = k.section_id
        WHERE s.grimoire_id = %s AND NOT sp.is_active
        """,
        (grimoire_id,),
    )
    rows = [dict(row) for row in cur.fetchall()]
    if rows:
        cur.execute(
            """
            UPDATE embedding e SET status = 'deleted', deleted_at = now(), updated_at = now()
            FROM semantic_projection sp, knowledge k, section s
            WHERE sp.semantic_projection_id = e.semantic_projection_id
              AND k.knowledge_id = sp.knowledge_id
              AND s.section_id = k.section_id
              AND s.grimoire_id = %s
              AND NOT sp.is_active
            """,
            (grimoire_id,),
        )
    return rows

def _queue_embeddings(cur, objects: dict[str, dict[str, Any]], embeddings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for entry in embeddings:
        object_key = _required_text(entry.get("object_source_key"), "embedding.object_source_key")
        context = objects.get(object_key)
        if context is None:
            raise HTTPException(status_code=422, detail=f"Unknown embedding object {object_key!r}")
        vector = entry.get("vector")
        if not isinstance(vector, list) or not vector or any(not isinstance(x, (int, float)) or not math.isfinite(float(x)) for x in vector):
            raise HTTPException(status_code=422, detail="Embedding vectors must contain finite numbers")
        model = entry.get("model") or {}
        collection = _required_text(model.get("qdrant_collection") or "knowledge-qwen3-embedding-4b", "embedding.model.qdrant_collection")
        distance = str(model.get("distance_metric") or "cosine").lower()
        if distance not in {"cosine", "dot", "euclid"}:
            raise HTTPException(status_code=422, detail="Unsupported embedding distance")
        cur.execute(
            """
            INSERT INTO embedding_model (
                provider, model_name, model_revision, vector_size,
                distance_metric, qdrant_collection, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (provider, model_name, model_revision) DO UPDATE SET
                vector_size = EXCLUDED.vector_size,
                distance_metric = EXCLUDED.distance_metric,
                qdrant_collection = EXCLUDED.qdrant_collection,
                is_active = true
            RETURNING embedding_model_id
            """,
            (
                str(model.get("provider") or "local"),
                _required_text(model.get("model_name"), "embedding.model.model_name"),
                str(model.get("model_revision") or ""),
                len(vector),
                distance,
                collection,
            ),
        )
        model_id = int(cur.fetchone()["embedding_model_id"])
        embedding_text = _required_text(entry.get("embedding_text"), "embedding.embedding_text")
        projection_type = _required_text(entry.get("projection_type"), "embedding.projection_type")
        structured = entry.get("structured_object") or {}
        content_hash = hashlib.sha256(
            _json({k: v for k, v in entry.items() if k != "vector"}).encode("utf-8")
        ).hexdigest()
        cur.execute(
            """
            INSERT INTO semantic_projection (
                knowledge_id, language_id, projection_type, direction,
                target_description, embedding_text, target_concepts,
                expected_target_types, specificity, grounding_kind,
                confidence, evidence, structured_object, generation_model,
                generation_prompt_version, content_hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s
            )
            ON CONFLICT (
                knowledge_id, language_id, projection_type, direction, content_hash
            ) DO UPDATE SET
                target_description = EXCLUDED.target_description,
                embedding_text = EXCLUDED.embedding_text,
                target_concepts = EXCLUDED.target_concepts,
                expected_target_types = EXCLUDED.expected_target_types,
                specificity = EXCLUDED.specificity,
                grounding_kind = EXCLUDED.grounding_kind,
                confidence = EXCLUDED.confidence,
                evidence = EXCLUDED.evidence,
                structured_object = EXCLUDED.structured_object,
                generation_model = EXCLUDED.generation_model,
                generation_prompt_version = EXCLUDED.generation_prompt_version,
                is_active = true,
                updated_at = now()
            RETURNING semantic_projection_id
            """,
            (
                context["knowledge_id"], context["language_id"], projection_type,
                str(entry.get("direction") or "self"),
                str(entry.get("target_description") or embedding_text),
                embedding_text,
                list(entry.get("target_concepts") or []),
                list(entry.get("expected_target_types") or []),
                str(entry.get("specificity") or "specific"),
                str(entry.get("grounding_kind") or "explicit"),
                entry.get("confidence"),
                _json(entry.get("evidence") or []),
                _json(structured),
                entry.get("generation_model"),
                entry.get("generation_prompt_version"),
                content_hash,
            ),
        )
        projection_id = int(cur.fetchone()["semantic_projection_id"])
        deterministic_id = uuid5(NAMESPACE_URL, f"theumst:{context['knowledge_id']}:{model_id}:{projection_id}")
        cur.execute(
            """
            INSERT INTO embedding (
                embedding_id, semantic_projection_id, embedding_model_id, status
            ) VALUES (%s, %s, %s, 'indexing')
            ON CONFLICT (semantic_projection_id, embedding_model_id) DO UPDATE SET
                status = 'indexing', deleted_at = NULL, last_error = NULL,
                updated_at = now()
            RETURNING embedding_id
            """,
            (str(deterministic_id), projection_id, model_id),
        )
        embedding_id = str(cur.fetchone()["embedding_id"])
        points.append({
            "embedding_id": embedding_id,
            "collection": collection,
            "vector_size": len(vector),
            "distance": distance,
            "vector": [float(x) for x in vector],
            "payload": {
                "embedding_id": embedding_id,
                "semantic_projection_id": projection_id,
                "knowledge_id": context["knowledge_id"],
                "language_id": context["language_id"],
                "section_id": context["section_id"],
                "grimoire_id": context["grimoire_id"],
                "working_type": context["working_type"],
                "projection_type": projection_type,
                "direction": str(entry.get("direction") or "self"),
                "object_source_key": object_key,
                "is_active": True,
            },
        })
    return points


def _store_images(
    *,
    archive_files: dict[str, bytes],
    images: list[dict[str, Any]],
    grimoire_id: int,
    sections: dict[str, int],
    objects: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    for image in images:
        source_id = _required_text(image.get("source_image_id"), "image.source_image_id")
        archive_path = _required_text(image.get("archive_path"), "image.archive_path")
        data = archive_files.get(archive_path)
        if data is None:
            raise HTTPException(status_code=422, detail=f"Missing image file {archive_path!r}")
        suffix = archive_path.rsplit(".", 1)[-1].lower() if "." in archive_path else "bin"
        if suffix not in {"jpg", "jpeg", "png", "webp", "gif", "svg"}:
            suffix = "bin"
        key = f"books/{grimoire_id}/images/{source_id}.{suffix}"
        storage.write_bytes(key, data)
        section_id = sections.get(str(image.get("section_source_key") or ""))
        object_context = objects.get(str(image.get("object_source_key") or ""))
        stored.append({
            "source_image_id": source_id,
            "storage_key": key,
            "url": storage.public_url(key),
            "section_id": section_id,
            "knowledge_id": object_context["knowledge_id"] if object_context else None,
            "semantic_context_name": image.get("semantic_context_name"),
            "metadata": image.get("metadata") or {},
        })
    return stored


def _finalize(points: list[dict[str, Any]], images: list[dict[str, Any]], grimoire_id: int) -> None:
    with transaction() as (_, cur):
        if points:
            cur.execute(
                """
                UPDATE embedding SET status = 'indexed', indexed_at = now(),
                    last_error = NULL, updated_at = now()
                WHERE embedding_id = ANY(%s::uuid[])
                """,
                ([point["embedding_id"] for point in points],),
            )
        for image in images:
            cur.execute(
                """
                INSERT INTO book_image (
                    grimoire_id, section_id, knowledge_id, source_image_id,
                    semantic_context_name, storage_key, url, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (grimoire_id, source_image_id) DO UPDATE SET
                    section_id = EXCLUDED.section_id,
                    knowledge_id = EXCLUDED.knowledge_id,
                    semantic_context_name = EXCLUDED.semantic_context_name,
                    storage_key = EXCLUDED.storage_key,
                    url = EXCLUDED.url,
                    metadata = EXCLUDED.metadata,
                    is_active = true,
                    updated_at = now()
                """,
                (
                    grimoire_id, image["section_id"], image["knowledge_id"],
                    image["source_image_id"], image["semantic_context_name"],
                    image["storage_key"], image["url"], _json(image["metadata"]),
                ),
            )


async def ingest_book_archive(upload: UploadFile) -> dict[str, Any]:
    data = await upload.read(MAX_ARCHIVE_BYTES + 1)
    manifest, files = _safe_archive(data)
    _validate_manifest(manifest)
    with transaction() as (_, cur):
        grimoire_id, language_id = _upsert_book(cur, manifest["book"])
        _deactivate_book_state(cur, grimoire_id)
        sections = _upsert_sections(cur, grimoire_id, language_id, manifest["sections"])
        objects = _upsert_objects(
            cur,
            grimoire_id=grimoire_id,
            language_id=language_id,
            sections=sections,
            objects=manifest["objects"],
        )
        points = _queue_embeddings(cur, objects, manifest["embeddings"])
        stale_points = _stale_embedding_points(cur, grimoire_id)

    try:
        stale_by_collection: dict[str, list[str]] = defaultdict(list)
        for point in stale_points:
            stale_by_collection[point["qdrant_collection"]].append(point["embedding_id"])
        for collection, point_ids in stale_by_collection.items():
            if qdrant_service.collection_exists(collection):
                qdrant_service.delete_many(collection=collection, point_ids=point_ids)

        grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
        for point in points:
            grouped[(point["collection"], point["vector_size"], point["distance"])].append(point)
        for (collection, vector_size, distance), group in grouped.items():
            qdrant_service.ensure_collection_config(
                collection=collection,
                vector_size=vector_size,
                distance=distance,
            )
            qdrant_service.upsert_many(
                collection=collection,
                points=group,
                vector_size=vector_size,
                chunk_size=512,
            )
        stored_images = _store_images(
            archive_files=files,
            images=manifest["images"],
            grimoire_id=grimoire_id,
            sections=sections,
            objects=objects,
        )
        _finalize(points, stored_images, grimoire_id)
    except Exception as exc:
        if points:
            with transaction() as (_, cur):
                cur.execute(
                    """
                    UPDATE embedding SET status = 'failed', last_error = %s,
                        updated_at = now()
                    WHERE embedding_id = ANY(%s::uuid[])
                    """,
                    (str(exc)[:4000], [point["embedding_id"] for point in points]),
                )
        raise

    return {
        "ok": True,
        "grimoire_id": grimoire_id,
        "book_source_key": manifest["book"]["source_key"],
        "section_count": len(sections),
        "object_count": len(objects),
        "embedding_count": len(points),
        "image_count": len(stored_images),
    }
