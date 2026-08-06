from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from ..config import get_settings
from ..database import transaction
from ..schemas import (
    BookReference,
    EmbeddingBatchInput,
    KnowledgeSubmission,
    SectionReference,
    SemanticEmbeddingInput,
)
from .qdrant import qdrant_service


def _resolve_book(cur, book: BookReference) -> int:
    if book.grimoire_id is not None:
        cur.execute("SELECT grimoire_id FROM grimoire WHERE grimoire_id = %s", (book.grimoire_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Book not found")
        return int(row["grimoire_id"])

    cur.execute(
        """
        SELECT grimoire_id FROM grimoire
        WHERE isbn IS NOT DISTINCT FROM %s
          AND publish_date IS NOT DISTINCT FROM %s
          AND version IS NOT DISTINCT FROM %s
        ORDER BY grimoire_id LIMIT 1
        """,
        (book.isbn, book.publish_date, book.version),
    )
    row = cur.fetchone()
    if row:
        return int(row["grimoire_id"])
    cur.execute(
        "INSERT INTO grimoire (isbn, publish_date, version) VALUES (%s, %s, %s) RETURNING grimoire_id",
        (book.isbn, book.publish_date, book.version),
    )
    return int(cur.fetchone()["grimoire_id"])


def _resolve_section(cur, grimoire_id: int, section: SectionReference) -> int:
    if section.section_id is not None:
        cur.execute(
            "SELECT section_id FROM section WHERE section_id = %s AND grimoire_id = %s",
            (section.section_id, grimoire_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Section not found in the specified book")
        return int(row["section_id"])

    cur.execute(
        """
        SELECT section_id FROM section
        WHERE grimoire_id = %s
          AND section_number = %s
          AND parent_section IS NOT DISTINCT FROM %s
        ORDER BY section_id LIMIT 1
        """,
        (grimoire_id, section.section_number, section.parent_section),
    )
    row = cur.fetchone()
    if row:
        return int(row["section_id"])
    cur.execute(
        """
        INSERT INTO section (parent_section, grimoire_id, section_number)
        VALUES (%s, %s, %s) RETURNING section_id
        """,
        (section.parent_section, grimoire_id, section.section_number),
    )
    return int(cur.fetchone()["section_id"])


def _embedding_model(cur, embedding: SemanticEmbeddingInput) -> tuple[int, str]:
    settings = get_settings()
    collection = embedding.model.qdrant_collection or settings.qdrant_collection
    if collection != settings.qdrant_collection:
        raise HTTPException(
            status_code=422,
            detail=f"This deployment accepts embeddings only in {settings.qdrant_collection!r}",
        )
    if embedding.model.distance_metric != settings.qdrant_distance:
        raise HTTPException(
            status_code=422,
            detail=f"Embedding distance must be {settings.qdrant_distance!r}",
        )
    if len(embedding.vector) != settings.qdrant_vector_size:
        raise HTTPException(
            status_code=422,
            detail=f"Embedding vector has {len(embedding.vector)} dimensions; expected {settings.qdrant_vector_size}",
        )
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
        RETURNING embedding_model_id, qdrant_collection
        """,
        (
            embedding.model.provider, embedding.model.model_name,
            embedding.model.model_revision, len(embedding.vector),
            embedding.model.distance_metric, collection,
        ),
    )
    row = cur.fetchone()
    return int(row["embedding_model_id"]), str(row["qdrant_collection"])


def _knowledge_embedding_context(cur, knowledge_id: int, language_id: int) -> dict[str, Any]:
    cur.execute(
        """
        SELECT k.knowledge_id, k.type AS working_type, k.section_id,
               s.grimoire_id, lk.language_id
        FROM knowledge k
        JOIN section s ON s.section_id = k.section_id
        JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id
            AND lk.language_id = %s
        WHERE k.knowledge_id = %s AND k.is_active
        """,
        (language_id, knowledge_id),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Knowledge object or requested language version not found",
        )
    return dict(row)


def _queue_embeddings(
    cur,
    *,
    context: dict[str, Any],
    embeddings: list[SemanticEmbeddingInput],
) -> list[dict[str, Any]]:
    pending_points: list[dict[str, Any]] = []
    for item in embeddings:
        model_id, collection = _embedding_model(cur, item)
        content_hash = item.content_hash()
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
                context["knowledge_id"], context["language_id"],
                item.projection_type, item.direction, item.target_description,
                item.embedding_text, item.target_concepts, item.expected_target_types,
                item.specificity, item.grounding_kind, item.confidence,
                __import__("json").dumps(item.evidence),
                __import__("json").dumps(item.structured_object),
                item.generation_model, item.generation_prompt_version,
                content_hash,
            ),
        )
        projection_id = int(cur.fetchone()["semantic_projection_id"])
        proposed_embedding_id = uuid4()
        cur.execute(
            """
            INSERT INTO embedding (
                embedding_id, semantic_projection_id, embedding_model_id, status
            ) VALUES (%s, %s, %s, 'pending')
            ON CONFLICT (semantic_projection_id, embedding_model_id) DO UPDATE SET
                status = 'pending', deleted_at = NULL, last_error = NULL,
                updated_at = now()
            RETURNING embedding_id
            """,
            (str(proposed_embedding_id), projection_id, model_id),
        )
        embedding_id = cur.fetchone()["embedding_id"]
        pending_points.append({
            "embedding_id": embedding_id,
            "semantic_projection_id": projection_id,
            "collection": collection,
            "vector": item.vector,
            "payload": {
                "embedding_id": str(embedding_id),
                "semantic_projection_id": projection_id,
                "knowledge_id": context["knowledge_id"],
                "language_id": context["language_id"],
                "section_id": context["section_id"],
                "grimoire_id": context["grimoire_id"],
                "working_type": context["working_type"],
                "projection_type": item.projection_type,
                "direction": item.direction,
                "expected_target_types": item.expected_target_types,
                "target_concepts": item.target_concepts,
                "specificity": item.specificity,
                "grounding_kind": item.grounding_kind,
                "confidence": item.confidence,
                "content_hash": content_hash,
                "is_active": True,
            },
        })
    return pending_points


def _index_pending_embeddings(points: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]]]:
    indexed: list[str] = []
    failed: list[dict[str, str]] = []
    for point in points:
        try:
            qdrant_service.upsert(
                point_id=point["embedding_id"],
                vector=point["vector"],
                payload=point["payload"],
                collection=point["collection"],
            )
            with transaction() as (_, cur):
                cur.execute(
                    """
                    UPDATE embedding SET status = 'indexed', indexed_at = now(),
                        last_error = NULL, updated_at = now()
                    WHERE embedding_id = %s
                    """,
                    (str(point["embedding_id"]),),
                )
            indexed.append(str(point["embedding_id"]))
        except Exception as exc:
            with transaction() as (_, cur):
                cur.execute(
                    """
                    UPDATE embedding SET status = 'failed', last_error = %s,
                        updated_at = now() WHERE embedding_id = %s
                    """,
                    (str(exc)[:4000], str(point["embedding_id"])),
                )
            failed.append({"embedding_id": str(point["embedding_id"]), "error": str(exc)})
    return indexed, failed


def submit_embeddings(knowledge_id: int, payload: EmbeddingBatchInput) -> dict[str, Any]:
    if not get_settings().qdrant_enabled:
        raise HTTPException(status_code=503, detail="Qdrant must be enabled when submitting embeddings")
    with transaction() as (_, cur):
        context = _knowledge_embedding_context(cur, knowledge_id, payload.language_id)
        pending_points = _queue_embeddings(cur, context=context, embeddings=payload.embeddings)
    indexed, failed = _index_pending_embeddings(pending_points)
    return {
        "knowledge_id": knowledge_id,
        "language_id": payload.language_id,
        "embeddings_indexed": indexed,
        "embeddings_failed": failed,
    }


def submit_knowledge(payload: KnowledgeSubmission) -> dict[str, Any]:
    if payload.embeddings and not get_settings().qdrant_enabled:
        raise HTTPException(status_code=503, detail="Qdrant must be enabled when submitting embeddings")

    with transaction() as (_, cur):
        grimoire_id = _resolve_book(cur, payload.book)
        section_id = _resolve_section(cur, grimoire_id, payload.section)
        cur.execute("SELECT language_id FROM language WHERE language_id = %s", (payload.knowledge.language_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Language not found")

        cur.execute(
            "INSERT INTO knowledge_crystal (likes) VALUES (%s) RETURNING knowledge_crystal_id",
            (payload.knowledge.likes,),
        )
        crystal_id = int(cur.fetchone()["knowledge_crystal_id"])
        cur.execute(
            """
            INSERT INTO knowledge (section_id, knowledge_crystal_id, type, is_default_in_crystal)
            VALUES (%s, %s, %s, %s) RETURNING knowledge_id
            """,
            (section_id, crystal_id, payload.knowledge.type, payload.knowledge.is_default_in_crystal),
        )
        knowledge_id = int(cur.fetchone()["knowledge_id"])
        cur.execute(
            """
            INSERT INTO language_knowledge (language_id, knowledge_id, working, statement)
            VALUES (%s, %s, %s, %s)
            """,
            (
                payload.knowledge.language_id, knowledge_id,
                payload.knowledge.working or "", payload.knowledge.statement,
            ),
        )
        context = {
            "knowledge_id": knowledge_id,
            "language_id": payload.knowledge.language_id,
            "section_id": section_id,
            "grimoire_id": grimoire_id,
            "working_type": payload.knowledge.type,
        }
        pending_points = _queue_embeddings(cur, context=context, embeddings=payload.embeddings)

    indexed, failed = _index_pending_embeddings(pending_points)
    return {
        "knowledge_id": knowledge_id,
        "knowledge_crystal_id": crystal_id,
        "grimoire_id": grimoire_id,
        "section_id": section_id,
        "embeddings_indexed": indexed,
        "embeddings_failed": failed,
    }


def list_knowledge(
    *,
    language_id: int,
    limit: int,
    offset: int,
    grimoire_id: int | None = None,
    section_id: int | None = None,
    working_type: str | None = None,
) -> list[dict[str, Any]]:
    conditions = ["lk.language_id = %s", "k.is_active"]
    params: list[Any] = [language_id]
    if grimoire_id is not None:
        conditions.append("s.grimoire_id = %s"); params.append(grimoire_id)
    if section_id is not None:
        conditions.append("k.section_id = %s"); params.append(section_id)
    if working_type:
        conditions.append("k.type = %s"); params.append(working_type)
    params.extend([limit, offset])
    with transaction() as (_, cur):
        cur.execute(
            f"""
            SELECT k.knowledge_id, k.type, k.is_default_in_crystal,
                   kc.likes, lk.language_id, lk.statement, lk.working,
                   lk.label, lk.working_summary, lk.ref_id,
                   lk.labelled_references, lk.object_reference_labels,
                   lk.loose_references_guessed_objects,
                   s.section_id, s.section_number, s.parent_section,
                   s.source_key AS section_source_key,
                   g.grimoire_id, g.source_key AS book_source_key,
                   g.isbn, g.publish_date, g.version
            FROM knowledge k
            JOIN knowledge_crystal kc ON kc.knowledge_crystal_id = k.knowledge_crystal_id
            JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id
            JOIN section s ON s.section_id = k.section_id
            JOIN grimoire g ON g.grimoire_id = s.grimoire_id
            WHERE {' AND '.join(conditions)}
            ORDER BY g.grimoire_id, s.section_id, k.knowledge_id
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
        return list(cur.fetchall())


def get_knowledge(knowledge_id: int, language_id: int) -> dict[str, Any]:
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT k.knowledge_id, k.type, k.is_default_in_crystal,
                   kc.likes, lk.language_id, lk.statement, lk.working,
                   lk.label, lk.working_summary, lk.ref_id,
                   lk.labelled_references, lk.object_reference_labels,
                   lk.loose_references_guessed_objects,
                   s.section_id, s.section_number, s.parent_section,
                   s.source_key AS section_source_key,
                   g.grimoire_id, g.source_key AS book_source_key,
                   g.isbn, g.publish_date, g.version,
                   COALESCE(jsonb_agg(
                       jsonb_build_object(
                           'semantic_projection_id', sp.semantic_projection_id,
                           'projection_type', sp.projection_type,
                           'direction', sp.direction,
                           'target_description', sp.target_description,
                           'target_concepts', sp.target_concepts,
                           'expected_target_types', sp.expected_target_types,
                           'specificity', sp.specificity,
                           'grounding_kind', sp.grounding_kind,
                           'confidence', sp.confidence
                       ) ORDER BY sp.semantic_projection_id
                   ) FILTER (WHERE sp.semantic_projection_id IS NOT NULL), '[]'::jsonb) AS projections,
                   COALESCE((
                       SELECT jsonb_agg(jsonb_build_object(
                           'book_image_id', bi.book_image_id,
                           'source_image_id', bi.source_image_id,
                           'semantic_context_name', bi.semantic_context_name,
                           'url', bi.url,
                           'metadata', bi.metadata
                       ) ORDER BY bi.book_image_id)
                       FROM book_image bi
                       WHERE bi.knowledge_id = k.knowledge_id AND bi.is_active
                   ), '[]'::jsonb) AS images
            FROM knowledge k
            JOIN knowledge_crystal kc ON kc.knowledge_crystal_id = k.knowledge_crystal_id
            JOIN language_knowledge lk ON lk.knowledge_id = k.knowledge_id AND lk.language_id = %s
            JOIN section s ON s.section_id = k.section_id
            JOIN grimoire g ON g.grimoire_id = s.grimoire_id
            LEFT JOIN semantic_projection sp ON sp.knowledge_id = k.knowledge_id
                AND sp.language_id = lk.language_id AND sp.is_active
            WHERE k.knowledge_id = %s AND k.is_active
            GROUP BY k.knowledge_id, kc.likes, lk.language_id, lk.statement, lk.working,
                     lk.label, lk.working_summary, lk.ref_id,
                     lk.labelled_references, lk.object_reference_labels,
                     lk.loose_references_guessed_objects,
                     s.section_id, s.source_key, g.grimoire_id, g.source_key
            """,
            (language_id, knowledge_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Knowledge object not found")
        return row
