
import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.services import storage


def test_local_storage_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVER", "LOCAL")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        storage.create_folder("books/artin")
        storage.write_bytes("books/artin/test.txt", b"hello")
        assert storage.read_bytes("books/artin/test.txt") == b"hello"
        items = storage.list_items("books/artin")
        assert items[0]["name"] == "test.txt"
        assert storage.health() == {"ok": True, "mode": "LOCAL"}
        storage.delete("books")
        assert not (tmp_path / "books").exists()
    finally:
        get_settings.cache_clear()


def test_storage_rejects_traversal():
    with pytest.raises(HTTPException):
        storage.clean_key("../secret")


def test_local_public_url_uses_public_api_prefix(monkeypatch):
    monkeypatch.setenv("SERVER", "LOCAL")
    monkeypatch.setenv("LOCAL_URL", "http://localhost:8080")
    get_settings.cache_clear()
    try:
        assert (
            storage.public_url("books/42/images/example image.png")
            == "http://localhost:8080/api/v1/storage/books/42/images/example%20image.png"
        )
    finally:
        get_settings.cache_clear()


def test_cloud_public_url_uses_stable_application_route(monkeypatch):
    monkeypatch.setenv("SERVER", "COM")
    monkeypatch.setenv("PUBLIC_WEBPAGE_URL", "https://theumst.example/")
    get_settings.cache_clear()
    try:
        assert (
            storage.public_url("books/42/images/example image.png")
            == "https://theumst.example/api/v1/storage/books/42/images/example%20image.png"
        )
    finally:
        get_settings.cache_clear()


def test_cloud_signed_read_url_uses_private_bucket(monkeypatch):
    class FakeClient:
        def generate_presigned_url(self, operation, *, Params, ExpiresIn):
            assert operation == "get_object"
            assert Params == {"Bucket": "private-books", "Key": "books/42/images/10.jpg"}
            assert ExpiresIn == 900
            return "https://signed.example/books/42/images/10.jpg"

    monkeypatch.setenv("SERVER", "COM")
    monkeypatch.setenv("DO_SPACES_BUCKET", "private-books")
    monkeypatch.setattr(storage, "_spaces_client", lambda: FakeClient())
    get_settings.cache_clear()
    try:
        assert (
            storage.signed_read_url("books/42/images/10.jpg")
            == "https://signed.example/books/42/images/10.jpg"
        )
    finally:
        get_settings.cache_clear()
