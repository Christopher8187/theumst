from __future__ import annotations

import hashlib
import gzip
import io
import json
import math
import zipfile
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, BinaryIO, Iterable, Iterator
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException, UploadFile
from psycopg2.extras import execute_values

from ..database import transaction
from . import storage
from .qdrant import qdrant_service

MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 20_000
MAX_OBJECTS = 500_000
MAX_EMBEDDINGS = 1_500_000
EMBEDDING_BATCH_SIZE = 256
DATABASE_BATCH_SIZE = 1_000
IMAGE_UPLOAD_WORKERS = 8


def _normalize_strings(value: Any) -> Any:
    """Replace database-forbidden NULs without disturbing other Unicode."""
    if isinstance(value, str):
        return value.replace("\x00", "\ufffd")
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = _normalize_strings(item)
        return value
    if isinstance(value, dict):
        for key in list(value):
            normalized_key = _normalize_strings(key)
            normalized_value = _normalize_strings(value[key])
            if normalized_key != key:
                if normalized_key in value:
                    raise HTTPException(status_code=422, detail="NUL normalization produced a duplicate JSON key")
                del value[key]
            value[normalized_key] = normalized_value
        return value
    return value


def _json(value: Any) -> str:
    return json.dumps(_normalize_strings(value), ensure_ascii=False, separators=(",", ":"))


@dataclass
class ArchiveBundle:
    archive: zipfile.ZipFile
    manifest: dict[str, Any]
    members: dict[str, zipfile.ZipInfo]

    def close(self) -> None:
        self.archive.close()


def _stream_size(stream: BinaryIO) -> int:
    position = stream.tell()
    stream.seek(0, io.SEEK_END)
    size = stream.tell()
    stream.seek(position)
    return size


def _open_archive(stream: BinaryIO) -> ArchiveBundle:
    size = _stream_size(stream)
    if not size:
        raise HTTPException(status_code=422, detail="The ingestion archive is empty")
    if size > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="The ingestion archive is too large")
    try:
        archive = zipfile.ZipFile(stream)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid ZIP archive") from exc

    entries = archive.infolist()
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        archive.close()
        raise HTTPException(status_code=413, detail="The archive contains too many entries")
    total = 0
    members: dict[str, zipfile.ZipInfo] = {}
    for member in entries:
        name = member.filename.replace("\\", "/").lstrip("/")
        parts = [part for part in name.split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            archive.close()
            raise HTTPException(status_code=422, detail=f"Unsafe archive member: {member.filename!r}")
        if member.is_dir():
            continue
        total += int(member.file_size)
        if total > MAX_UNCOMPRESSED_BYTES:
            archive.close()
            raise HTTPException(status_code=413, detail="The uncompressed archive is too large")
        normalized = "/".join(parts)
        if normalized in members:
            archive.close()
            raise HTTPException(status_code=422, detail=f"Duplicate archive member: {normalized!r}")
        members[normalized] = member
    try:
        manifest_member = members.pop("manifest.json")
        with archive.open(manifest_member) as raw, io.TextIOWrapper(raw, encoding="utf-8") as text:
            manifest = _normalize_strings(json.load(text))
    except KeyError as exc:
        archive.close()
        raise HTTPException(status_code=422, detail="manifest.json is missing") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        archive.close()
        raise HTTPException(status_code=422, detail="manifest.json is invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") not in {1, 2}:
        archive.close()
        raise HTTPException(status_code=422, detail="Unsupported ingestion manifest")
    return ArchiveBundle(archive=archive, manifest=manifest, members=members)


def _safe_archive(data: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Compatibility helper for small fixtures; production ingestion stays streamed."""
    bundle = _open_archive(io.BytesIO(data))
    try:
        return bundle.manifest, {
            name: bundle.archive.read(member)
            for name, member in bundle.members.items()
        }
    finally:
        bundle.close()


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
    if not isinstance(images, list):
        raise HTTPException(status_code=422, detail="images must be an array")
    if isinstance(embeddings, dict):
        _required_text(embeddings.get("archive_path"), "embeddings.archive_path")
        if embeddings.get("format") not in (None, "json-array"):
            raise HTTPException(status_code=422, detail="Unsupported embeddings format")
        if embeddings.get("compression") not in (None, "gzip"):
            raise HTTPException(status_code=422, detail="Unsupported embeddings compression")
        embedding_count = int(embeddings.get("count") or 0)
    elif isinstance(embeddings, list):
        embedding_count = len(embeddings)
    else:
        raise HTTPException(status_code=422, detail="embeddings must be an array or archive descriptor")
    if len(objects) > MAX_OBJECTS or embedding_count > MAX_EMBEDDINGS:
        raise HTTPException(status_code=413, detail="The manifest contains too many records")


def _iter_json_array(stream: io.TextIOBase) -> Iterator[dict[str, Any]]:
    decoder = json.JSONDecoder()
    buffer = ""
    started = False
    expect_separator = False
    eof = False

    while True:
        if not eof and len(buffer) < 65_536:
            chunk = stream.read(65_536)
            if chunk:
                buffer += chunk
            else:
                eof = True
        buffer = buffer.lstrip()
        if not started:
            if not buffer and not eof:
                continue
            if not buffer or buffer[0] != "[":
                raise HTTPException(status_code=422, detail="The embeddings sidecar must contain a JSON array")
            buffer = buffer[1:]
            started = True
            continue
        buffer = buffer.lstrip()
        if expect_separator:
            if not buffer and not eof:
                continue
            if buffer.startswith(","):
                buffer = buffer[1:]
                expect_separator = False
                continue
            if buffer.startswith("]"):
                buffer = buffer[1:]
                trailing = buffer + stream.read()
                if trailing.strip():
                    raise HTTPException(status_code=422, detail="The embeddings sidecar has trailing content")
                return
            raise HTTPException(status_code=422, detail="The embeddings sidecar is not a valid JSON array")
        if not buffer and not eof:
            continue
        if buffer.startswith("]"):
            buffer = buffer[1:]
            trailing = buffer + stream.read()
            if trailing.strip():
                raise HTTPException(status_code=422, detail="The embeddings sidecar has trailing content")
            return
        try:
            value, end = decoder.raw_decode(buffer)
        except json.JSONDecodeError as exc:
            if not eof:
                chunk = stream.read(65_536)
                if chunk:
                    buffer += chunk
                    continue
                eof = True
                continue
            raise HTTPException(status_code=422, detail="The embeddings sidecar is invalid") from exc
        if not isinstance(value, dict):
            raise HTTPException(status_code=422, detail="Every embedding record must be an object")
        yield _normalize_strings(value)
        buffer = buffer[end:]
        expect_separator = True


def _embedding_entries(bundle: ArchiveBundle) -> Iterator[dict[str, Any]]:
    descriptor = bundle.manifest["embeddings"]
    if isinstance(descriptor, list):
        yield from descriptor
        return
    archive_path = _required_text(descriptor.get("archive_path"), "embeddings.archive_path")
    member = bundle.members.get(archive_path)
    if member is None:
        raise HTTPException(status_code=422, detail=f"Missing embeddings file {archive_path!r}")
    with bundle.archive.open(member) as archived:
        if descriptor.get("compression") == "gzip" or archive_path.endswith(".gz"):
            binary: BinaryIO = gzip.GzipFile(fileobj=archived)
        else:
            binary = archived
        with binary, io.TextIOWrapper(binary, encoding="utf-8") as text:
            yield from _iter_json_array(text)


def _batches(entries: Iterable[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    count = 0
    for entry in entries:
        count += 1
        if count > MAX_EMBEDDINGS:
            raise HTTPException(status_code=413, detail="The manifest contains too many embedding records")
        batch.append(entry)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


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
    if not sections:
        return {}
    language_rows: list[tuple[Any, ...]] = []
    section_by_key: dict[str, dict[str, Any]] = {}
    for section in sections:
        source_key = _required_text(section.get("source_key"), "section.source_key")
        if source_key in section_by_key:
            raise HTTPException(status_code=422, detail=f"Duplicate section source_key {source_key!r}")
        section_by_key[source_key] = section
    for source_key, section in section_by_key.items():
        parent_key = section.get("parent_source_key")
        if parent_key and str(parent_key) not in section_by_key:
            raise HTTPException(status_code=422, detail=f"Unknown parent section {parent_key!r}")

    # The legacy uniqueness constraint includes parent_section. Insert one
    # hierarchy level at a time so children never temporarily appear as roots;
    # roots and children are still batched within each level.
    result: dict[str, int] = {}
    remaining = dict(section_by_key)
    while remaining:
        level = [
            (source_key, section)
            for source_key, section in remaining.items()
            if not section.get("parent_source_key")
            or str(section["parent_source_key"]) in result
        ]
        if not level:
            cycle = ", ".join(sorted(remaining)[:10])
            raise HTTPException(status_code=422, detail=f"Section hierarchy contains a cycle near {cycle}")
        prepared = []
        for source_key, section in level:
            parent_key = section.get("parent_source_key")
            prepared.append((
                result.get(str(parent_key)) if parent_key else None,
                grimoire_id,
                _required_text(section.get("section_number") or source_key, "section.section_number"),
                source_key,
                _json(section.get("metadata") or {}),
            ))
        rows = execute_values(
            cur,
            """
            INSERT INTO section (parent_section, grimoire_id, section_number, source_key, source_metadata)
            VALUES %s
            ON CONFLICT (grimoire_id, source_key) WHERE source_key IS NOT NULL DO UPDATE SET
                parent_section = EXCLUDED.parent_section,
                section_number = EXCLUDED.section_number,
                source_metadata = EXCLUDED.source_metadata
            RETURNING section_id, source_key
            """,
            prepared,
            template="(%s, %s, %s, %s, %s::jsonb)",
            page_size=DATABASE_BATCH_SIZE,
            fetch=True,
        )
        for row in rows:
            result[str(row["source_key"])] = int(row["section_id"])
        for source_key, _ in level:
            del remaining[source_key]

    for section in sections:
        source_key = str(section["source_key"])
        language_rows.append((
            language_id,
            result[source_key],
            section.get("section_name"),
            section.get("section_head"),
            section.get("section_tail"),
        ))
    execute_values(
        cur,
        """
        INSERT INTO language_section (
            language_id, section_id, section_name, section_head, section_tail
        ) VALUES %s
        ON CONFLICT (language_id, section_id) DO UPDATE SET
            section_name = EXCLUDED.section_name,
            section_head = EXCLUDED.section_head,
            section_tail = EXCLUDED.section_tail
        """,
        language_rows,
        page_size=DATABASE_BATCH_SIZE,
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
    if not objects:
        return {}

    prepared: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for obj in objects:
        source_key = _required_text(obj.get("source_key"), "object.source_key")
        section_key = _required_text(obj.get("section_source_key"), "object.section_source_key")
        section_id = sections.get(section_key)
        if section_id is None:
            raise HTTPException(status_code=422, detail=f"Unknown section {section_key!r}")
        identity = (section_id, source_key)
        if identity in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate object source_key {source_key!r} in section {section_key!r}")
        seen.add(identity)
        prepared.append({
            "source": obj,
            "source_key": source_key,
            "section_id": section_id,
            "working_type": str(obj.get("type") or "just a statement"),
            "likes": max(0, int(obj.get("likes") or 0)),
        })

    cur.execute(
        """
        SELECT k.knowledge_id, k.knowledge_crystal_id, k.section_id, k.source_key
        FROM knowledge k
        JOIN section s ON s.section_id = k.section_id
        WHERE s.grimoire_id = %s AND k.source_key IS NOT NULL
        """,
        (grimoire_id,),
    )
    existing = {
        (int(row["section_id"]), str(row["source_key"])): {
            "knowledge_id": int(row["knowledge_id"]),
            "knowledge_crystal_id": int(row["knowledge_crystal_id"]),
        }
        for row in cur.fetchall()
    }
    new_rows = [row for row in prepared if (row["section_id"], row["source_key"]) not in existing]
    if new_rows:
        cur.execute(
            """
            SELECT nextval(pg_get_serial_sequence('knowledge_crystal', 'knowledge_crystal_id'))
                   AS knowledge_crystal_id
            FROM generate_series(1, %s)
            """,
            (len(new_rows),),
        )
        crystal_ids = [int(row["knowledge_crystal_id"]) for row in cur.fetchall()]
        for row, crystal_id in zip(new_rows, crystal_ids, strict=True):
            row["knowledge_crystal_id"] = crystal_id
        execute_values(
            cur,
            "INSERT INTO knowledge_crystal (knowledge_crystal_id, likes) VALUES %s",
            [(row["knowledge_crystal_id"], row["likes"]) for row in new_rows],
            page_size=DATABASE_BATCH_SIZE,
        )

    knowledge_rows: list[tuple[Any, ...]] = []
    crystal_likes: list[tuple[int, int]] = []
    for row in prepared:
        identity = (row["section_id"], row["source_key"])
        current = existing.get(identity)
        crystal_id = current["knowledge_crystal_id"] if current else row["knowledge_crystal_id"]
        obj = row["source"]
        knowledge_rows.append((
            row["section_id"], crystal_id, row["working_type"],
            bool(obj.get("is_default_in_crystal", True)), row["source_key"],
            _json(obj.get("source_metadata") or {}),
        ))
        crystal_likes.append((crystal_id, row["likes"]))

    returned = execute_values(
        cur,
        """
        INSERT INTO knowledge (
            section_id, knowledge_crystal_id, type, is_default_in_crystal,
            source_key, source_metadata, is_active
        ) VALUES %s
        ON CONFLICT (section_id, source_key) WHERE source_key IS NOT NULL DO UPDATE SET
            type = EXCLUDED.type,
            is_default_in_crystal = EXCLUDED.is_default_in_crystal,
            source_metadata = EXCLUDED.source_metadata,
            is_active = true
        RETURNING knowledge_id, section_id, source_key
        """,
        knowledge_rows,
        template="(%s, %s, %s, %s, %s, %s::jsonb, true)",
        page_size=DATABASE_BATCH_SIZE,
        fetch=True,
    )
    knowledge_ids = {
        (int(row["section_id"]), str(row["source_key"])): int(row["knowledge_id"])
        for row in returned
    }
    execute_values(
        cur,
        """
        UPDATE knowledge_crystal AS crystal
        SET likes = values.likes
        FROM (VALUES %s) AS values(knowledge_crystal_id, likes)
        WHERE crystal.knowledge_crystal_id = values.knowledge_crystal_id
        """,
        crystal_likes,
        page_size=DATABASE_BATCH_SIZE,
    )

    language_rows: list[tuple[Any, ...]] = []
    result: dict[str, dict[str, Any]] = {}
    for row in prepared:
        obj = row["source"]
        knowledge_id = knowledge_ids[(row["section_id"], row["source_key"])]
        language_rows.append((
            language_id, knowledge_id, str(obj.get("working") or ""),
            _required_text(obj.get("statement"), "object.statement"), obj.get("label"),
            obj.get("working_summary"), obj.get("ref_id"),
            _json(obj.get("labelled_references") or []),
            _json(obj.get("object_reference_labels") or []),
            _json(obj.get("loose_references_guessed_objects") or []),
            _json(obj.get("language_metadata") or {}),
        ))
        result[row["source_key"]] = {
            "knowledge_id": knowledge_id,
            "section_id": row["section_id"],
            "grimoire_id": grimoire_id,
            "language_id": language_id,
            "working_type": row["working_type"],
        }
    execute_values(
        cur,
        """
        INSERT INTO language_knowledge (
            language_id, knowledge_id, working, statement, label,
            working_summary, ref_id, labelled_references,
            object_reference_labels, loose_references_guessed_objects,
            source_metadata
        ) VALUES %s
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
        language_rows,
        template="(%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)",
        page_size=DATABASE_BATCH_SIZE,
    )
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

def _queue_embeddings(
    cur,
    objects: dict[str, dict[str, Any]],
    embeddings: list[dict[str, Any]],
    model_cache: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    pending_configs: dict[tuple[str, str, str], tuple[int, str, str]] = {}
    for entry in embeddings:
        object_key = _required_text(
            entry.get("object_source_key") or entry.get("local_object_id"),
            "embedding.object_source_key",
        )
        context = objects.get(object_key)
        if context is None:
            raise HTTPException(status_code=422, detail=f"Unknown embedding object {object_key!r}")
        vector = entry.get("vector")
        if not isinstance(vector, list) or not vector or any(not isinstance(x, (int, float)) or not math.isfinite(float(x)) for x in vector):
            raise HTTPException(status_code=422, detail="Embedding vectors must contain finite numbers")
        model = entry.get("model") or {}
        collection = _required_text(model.get("qdrant_collection") or "knowledge-qwen3-embedding-0-6b", "embedding.model.qdrant_collection")
        distance = str(model.get("distance_metric") or "cosine").lower()
        if distance not in {"cosine", "dot", "euclid"}:
            raise HTTPException(status_code=422, detail="Unsupported embedding distance")
        provider = str(model.get("provider") or "local")
        model_name = _required_text(model.get("model_name"), "embedding.model.model_name")
        model_revision = str(model.get("model_revision") or "")
        model_key = (provider, model_name, model_revision)
        config = (len(vector), distance, collection)
        cached = model_cache.get(model_key)
        if cached and (cached["vector_size"], cached["distance"], cached["collection"]) != config:
            raise HTTPException(status_code=422, detail=f"Embedding model {model_name!r} has inconsistent configuration")
        pending = pending_configs.setdefault(model_key, config)
        if pending != config:
            raise HTTPException(status_code=422, detail=f"Embedding model {model_name!r} has inconsistent configuration")
        embedding_text = _required_text(entry.get("embedding_text"), "embedding.embedding_text")
        projection_type = _required_text(entry.get("projection_type"), "embedding.projection_type")
        structured = entry.get("structured_object") or {
            "view": projection_type,
            "source": "kaicenat-embed",
        }
        normalized = dict(entry)
        normalized.pop("vector", None)
        normalized.pop("local_object_id", None)
        normalized["object_source_key"] = object_key
        normalized.setdefault("specificity", "specific")
        normalized.setdefault("grounding_kind", "explicit")
        normalized.setdefault("structured_object", structured)
        content_hash = hashlib.sha256(
            _json(normalized).encode("utf-8")
        ).hexdigest()
        prepared.append({
            "entry": entry,
            "context": context,
            "object_key": object_key,
            "vector": vector,
            "vector_size": len(vector),
            "distance": distance,
            "collection": collection,
            "model_key": model_key,
            "embedding_text": embedding_text,
            "projection_type": projection_type,
            "structured": structured,
            "content_hash": content_hash,
        })

    for row in prepared:
        model_key = row["model_key"]
        if model_key in model_cache:
            continue
        provider, model_name, model_revision = model_key
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
                is_active = true,
                created_at = embedding_model.created_at
            RETURNING embedding_model_id
            """,
            (
                provider, model_name, model_revision, row["vector_size"],
                row["distance"], row["collection"],
            ),
        )
        model_cache[model_key] = {
            "model_id": int(cur.fetchone()["embedding_model_id"]),
            "vector_size": row["vector_size"],
            "distance": row["distance"],
            "collection": row["collection"],
        }

    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in prepared:
        context = row["context"]
        entry = row["entry"]
        projection_key = (
            context["knowledge_id"], context["language_id"], row["projection_type"],
            str(entry.get("direction") or "self"), row["content_hash"],
        )
        unique[projection_key] = row
    prepared = list(unique.values())
    projection_rows = []
    for row in prepared:
        context = row["context"]
        entry = row["entry"]
        projection_rows.append((
            context["knowledge_id"], context["language_id"], row["projection_type"],
            str(entry.get("direction") or "self"),
            str(entry.get("target_description") or row["embedding_text"]),
            row["embedding_text"], list(entry.get("target_concepts") or []),
            list(entry.get("expected_target_types") or []),
            str(entry.get("specificity") or "specific"),
            str(entry.get("grounding_kind") or "explicit"), entry.get("confidence"),
            _json(entry.get("evidence") or []), _json(row["structured"]),
            entry.get("generation_model"), entry.get("generation_prompt_version"),
            row["content_hash"],
        ))
    projection_results = execute_values(
        cur,
        """
        INSERT INTO semantic_projection (
            knowledge_id, language_id, projection_type, direction,
            target_description, embedding_text, target_concepts,
            expected_target_types, specificity, grounding_kind,
            confidence, evidence, structured_object, generation_model,
            generation_prompt_version, content_hash
        ) VALUES %s
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
        RETURNING semantic_projection_id, knowledge_id, language_id,
                  projection_type, direction, content_hash
        """,
        projection_rows,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)",
        page_size=DATABASE_BATCH_SIZE,
        fetch=True,
    )
    projection_ids = {
        (
            int(result["knowledge_id"]), int(result["language_id"]),
            str(result["projection_type"]), str(result["direction"]), str(result["content_hash"]),
        ): int(result["semantic_projection_id"])
        for result in projection_results
    }
    embedding_rows = []
    for row in prepared:
        context = row["context"]
        entry = row["entry"]
        projection_key = (
            context["knowledge_id"], context["language_id"], row["projection_type"],
            str(entry.get("direction") or "self"), row["content_hash"],
        )
        projection_id = projection_ids[projection_key]
        model_id = model_cache[row["model_key"]]["model_id"]
        deterministic_id = uuid5(NAMESPACE_URL, f"theumst:{context['knowledge_id']}:{model_id}:{projection_id}")
        row["projection_id"] = projection_id
        row["model_id"] = model_id
        row["deterministic_id"] = str(deterministic_id)
        embedding_rows.append((str(deterministic_id), projection_id, model_id))
    embedding_results = execute_values(
        cur,
        """
        INSERT INTO embedding (
            embedding_id, semantic_projection_id, embedding_model_id, status
        ) VALUES %s
        ON CONFLICT (semantic_projection_id, embedding_model_id) DO UPDATE SET
            status = 'indexing', deleted_at = NULL, last_error = NULL,
            updated_at = now()
        RETURNING embedding_id, semantic_projection_id, embedding_model_id
        """,
        embedding_rows,
        template="(%s, %s, %s, 'indexing')",
        page_size=DATABASE_BATCH_SIZE,
        fetch=True,
    )
    embedding_ids = {
        (int(result["semantic_projection_id"]), int(result["embedding_model_id"])): str(result["embedding_id"])
        for result in embedding_results
    }
    points: list[dict[str, Any]] = []
    for row in prepared:
        context = row["context"]
        entry = row["entry"]
        projection_id = row["projection_id"]
        embedding_id = embedding_ids[(projection_id, row["model_id"])]
        points.append({
            "embedding_id": embedding_id,
            "collection": row["collection"],
            "vector_size": row["vector_size"],
            "distance": row["distance"],
            "vector": row["vector"],
            "payload": {
                "embedding_id": embedding_id,
                "semantic_projection_id": projection_id,
                "knowledge_id": context["knowledge_id"],
                "language_id": context["language_id"],
                "section_id": context["section_id"],
                "grimoire_id": context["grimoire_id"],
                "working_type": context["working_type"],
                "projection_type": row["projection_type"],
                "direction": str(entry.get("direction") or "self"),
                "object_source_key": row["object_key"],
                "is_active": True,
            },
        })
    return points


def _store_images(
    *,
    bundle: ArchiveBundle,
    images: list[dict[str, Any]],
    grimoire_id: int,
    sections: dict[str, int],
    objects: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    def store_one(index: int, image: dict[str, Any], data: bytes) -> tuple[int, dict[str, Any]]:
        source_id = _required_text(image.get("source_image_id"), "image.source_image_id")
        archive_path = _required_text(image.get("archive_path"), "image.archive_path")
        suffix = archive_path.rsplit(".", 1)[-1].lower() if "." in archive_path else "bin"
        if suffix not in {"jpg", "jpeg", "png", "webp", "gif", "svg"}:
            suffix = "bin"
        key = f"books/{grimoire_id}/images/{source_id}.{suffix}"
        storage.write_bytes(key, data)
        section_id = sections.get(str(image.get("section_source_key") or ""))
        object_context = objects.get(str(image.get("object_source_key") or ""))
        return index, {
            "source_image_id": source_id,
            "storage_key": key,
            "url": storage.public_url(key),
            "section_id": section_id,
            "knowledge_id": object_context["knowledge_id"] if object_context else None,
            "semantic_context_name": image.get("semantic_context_name"),
            "metadata": image.get("metadata") or {},
        }

    for image in images:
        archive_path = _required_text(image.get("archive_path"), "image.archive_path")
        if archive_path not in bundle.members:
            raise HTTPException(status_code=422, detail=f"Missing image file {archive_path!r}")

    stored: dict[int, dict[str, Any]] = {}
    pending: set[Future] = set()
    workers = max(1, min(IMAGE_UPLOAD_WORKERS, len(images)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="book-image-upload") as pool:
        for index, image in enumerate(images):
            archive_path = str(image["archive_path"])
            data = bundle.archive.read(bundle.members[archive_path])
            pending.add(pool.submit(store_one, index, image, data))
            if len(pending) >= workers:
                complete, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in complete:
                    result_index, result = future.result()
                    stored[result_index] = result
        for future in pending:
            result_index, result = future.result()
            stored[result_index] = result
    return [stored[index] for index in range(len(images))]


def _set_embedding_status(points: list[dict[str, Any]], status: str, error: str | None = None) -> None:
    if not points:
        return
    with transaction() as (_, cur):
        indexed_at = "now()" if status == "indexed" else "indexed_at"
        cur.execute(
            f"""
            UPDATE embedding SET status = %s, indexed_at = {indexed_at},
                last_error = %s, updated_at = now()
            WHERE embedding_id = ANY(%s::uuid[])
            """,
            (status, error, [point["embedding_id"] for point in points]),
        )


def _finalize_images(images: list[dict[str, Any]], grimoire_id: int) -> None:
    if not images:
        return
    with transaction() as (_, cur):
        execute_values(
            cur,
            """
            INSERT INTO book_image (
                grimoire_id, section_id, knowledge_id, source_image_id,
                semantic_context_name, storage_key, url, metadata
            ) VALUES %s
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
            [(
                grimoire_id, image["section_id"], image["knowledge_id"],
                image["source_image_id"], image["semantic_context_name"],
                image["storage_key"], image["url"], _json(image["metadata"]),
            ) for image in images],
            template="(%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            page_size=DATABASE_BATCH_SIZE,
        )


async def ingest_book_archive(upload: UploadFile) -> dict[str, Any]:
    await upload.seek(0)
    bundle = _open_archive(upload.file)
    try:
        manifest = bundle.manifest
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
            stale_points = _stale_embedding_points(cur, grimoire_id)

        stale_by_collection: dict[str, list[str]] = defaultdict(list)
        for point in stale_points:
            stale_by_collection[point["qdrant_collection"]].append(point["embedding_id"])
        for collection, point_ids in stale_by_collection.items():
            if qdrant_service.collection_exists(collection):
                qdrant_service.delete_many(collection=collection, point_ids=point_ids)

        model_cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        ensured_collections: set[tuple[str, int, str]] = set()
        embedding_count = 0
        for embedding_batch in _batches(_embedding_entries(bundle), EMBEDDING_BATCH_SIZE):
            points: list[dict[str, Any]] = []
            try:
                with transaction() as (_, cur):
                    points = _queue_embeddings(cur, objects, embedding_batch, model_cache)
                grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
                for point in points:
                    grouped[(point["collection"], point["vector_size"], point["distance"])].append(point)
                for (collection, vector_size, distance), group in grouped.items():
                    config = (collection, vector_size, distance)
                    if config not in ensured_collections:
                        qdrant_service.ensure_collection_config(
                            collection=collection,
                            vector_size=vector_size,
                            distance=distance,
                        )
                        ensured_collections.add(config)
                    qdrant_service.upsert_many(
                        collection=collection,
                        points=group,
                        vector_size=vector_size,
                        chunk_size=EMBEDDING_BATCH_SIZE,
                    )
                _set_embedding_status(points, "indexed")
                embedding_count += len(points)
            except Exception as exc:
                _set_embedding_status(points, "failed", str(exc)[:4000])
                raise
        descriptor = manifest["embeddings"]
        if isinstance(descriptor, dict) and descriptor.get("count") is not None:
            expected = int(descriptor["count"])
            if embedding_count != expected:
                raise HTTPException(
                    status_code=422,
                    detail=f"Embeddings sidecar contains {embedding_count} records; expected {expected}",
                )
        stored_images = _store_images(
            bundle=bundle,
            images=manifest["images"],
            grimoire_id=grimoire_id,
            sections=sections,
            objects=objects,
        )
        _finalize_images(stored_images, grimoire_id)
    finally:
        bundle.close()

    return {
        "ok": True,
        "grimoire_id": grimoire_id,
        "book_source_key": manifest["book"]["source_key"],
        "section_count": len(sections),
        "object_count": len(objects),
        "embedding_count": embedding_count,
        "image_count": len(stored_images),
    }
