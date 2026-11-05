from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import public_api


def test_regular_and_master_page_caps(monkeypatch):
    monkeypatch.setattr(public_api, "list_knowledge", lambda **kwargs: [{"knowledge_id": 1}])
    request = SimpleNamespace()
    kinds = []

    def regular(request, **options):
        kinds.append(options.get("kind"))
        return {"key_type": "regular", "rate_remaining": 599}

    monkeypatch.setattr(public_api, "authenticate_api_key", regular)
    with pytest.raises(HTTPException, match="limit may not exceed 100"):
        public_api.read_knowledge_collection(request, 1, 101, 0, None, None, None)

    monkeypatch.setattr(
        public_api, "authenticate_api_key",
        lambda request, **options: {"key_type": "master", "rate_remaining": None},
    )
    result = public_api.read_knowledge_collection(request, 1, 1000, 0, None, None, None)
    assert result["key_type"] == "master"
    assert result["items"][0]["knowledge_id"] == 1
    assert kinds == ["book"]


def test_every_public_api_key_check_counts_as_a_book_request():
    source = Path(public_api.__file__).read_text(encoding="utf-8")
    calls = source.count("authenticate_api_key(request")
    assert calls == 8
    assert source.count('authenticate_api_key(request, kind="book"') == calls
