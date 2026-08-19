from __future__ import annotations

import io
import gzip
import json
import zipfile
from pathlib import Path

import httpx
import pytest

from app.config import get_settings
from app.main import create_app
from app.services.book_ingestion import MAX_ARCHIVE_BYTES, _embedding_entries, _open_archive, _safe_archive
from app.services.qdrant import QdrantService


def archive_bytes(manifest: dict, files: dict[str, bytes] | None = None) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, data in (files or {}).items():
            archive.writestr(name, data)
    return output.getvalue()


def minimal_manifest() -> dict:
    return {
        "schema_version": 1,
        "book": {"source_key": "book", "title": "Book"},
        "sections": [],
        "objects": [],
        "embeddings": [],
        "images": [],
    }


def test_whole_book_archive_limit_is_one_gibibyte():
    assert MAX_ARCHIVE_BYTES == 1024 * 1024 * 1024


def test_archive_parser_reads_one_manifest_and_files():
    manifest, files = _safe_archive(
        archive_bytes(minimal_manifest(), {"images/image_1.jpg": b"jpg"})
    )
    assert manifest["book"]["source_key"] == "book"
    assert files == {"images/image_1.jpg": b"jpg"}


def test_archive_parser_rejects_path_traversal():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("manifest.json", json.dumps(minimal_manifest()))
        archive.writestr("../secret.txt", "bad")
    with pytest.raises(Exception, match="Unsafe archive member"):
        _safe_archive(output.getvalue())


def test_v2_archive_streams_gzipped_embedding_sidecar():
    manifest = minimal_manifest()
    manifest["schema_version"] = 2
    manifest["embeddings"] = {
        "archive_path": "embeddings/records.json.gz",
        "format": "json-array",
        "compression": "gzip",
        "count": 2,
    }
    records = [
        {"local_object_id": "one", "vector": [0.1, 0.2]},
        {"local_object_id": "two", "vector": [0.3, 0.4]},
    ]
    payload = archive_bytes(
        manifest,
        {"embeddings/records.json.gz": gzip.compress(json.dumps(records).encode("utf-8"))},
    )
    bundle = _open_archive(io.BytesIO(payload))
    try:
        assert list(_embedding_entries(bundle)) == records
    finally:
        bundle.close()


def test_archive_boundary_replaces_database_forbidden_nuls():
    manifest = minimal_manifest()
    manifest["schema_version"] = 2
    manifest["book"]["title"] = "Bad\x00Book"
    manifest["embeddings"] = {
        "archive_path": "embeddings/records.json.gz",
        "format": "json-array",
        "compression": "gzip",
        "count": 1,
    }
    records = [{"local_object_id": "one", "embedding_text": "bad\x00text", "vector": [0.1]}]
    payload = archive_bytes(
        manifest,
        {"embeddings/records.json.gz": gzip.compress(json.dumps(records).encode("utf-8"))},
    )
    bundle = _open_archive(io.BytesIO(payload))
    try:
        assert bundle.manifest["book"]["title"] == "Bad�Book"
        assert list(_embedding_entries(bundle))[0]["embedding_text"] == "bad�text"
    finally:
        bundle.close()


def test_master_archive_route_is_registered():
    app = create_app(initialize_services=False)
    paths = {route.path for route in app.routes}
    assert "/api/v1/books/ingest-archive" in paths


def test_qdrant_batch_upsert_is_one_request_for_one_chunk(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": {"status": "completed"}})

    settings = get_settings()
    client = httpx.Client(
        base_url="http://qdrant.test",
        transport=httpx.MockTransport(handler),
    )
    service = QdrantService(settings=settings, client=client)
    service.upsert_many(
        collection="knowledge-qwen3-embedding-0-6b",
        vector_size=3,
        points=[
            {"embedding_id": "00000000-0000-0000-0000-000000000001", "vector": [1, 0, 0], "payload": {"knowledge_id": 1}},
            {"embedding_id": "00000000-0000-0000-0000-000000000002", "vector": [0, 1, 0], "payload": {"knowledge_id": 2}},
        ],
    )
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert len(body["points"]) == 2


def test_schema_supports_idempotent_book_ingestion_and_images():
    root = Path(__file__).resolve().parents[3]
    sql = (root / "backend" / "sql" / "002_book_ingestion.sql").read_text()
    assert "grimoire_source_key_unique" in sql
    assert "knowledge_section_source_key_unique" in sql
    assert "CREATE TABLE IF NOT EXISTS book_image" in sql
    assert "working_summary" in sql


def test_website_does_not_embed_the_publisher_master_key():
    root = Path(__file__).resolve().parents[3]
    secret = "umst_read__" + "TndzLuS_XC6lBGibv5M5apryXAbBo0KesZIiJpXClI"
    for path in root.rglob("*"):
        if not path.is_file() or path.name == ".env":
            continue
        if any(part in {".pytest_cache", "__pycache__", "node_modules", "dist"} for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        assert secret not in content, path
