from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import public_api


def test_regular_and_master_page_caps(monkeypatch):
    monkeypatch.setattr(public_api, "list_knowledge", lambda **kwargs: [{"knowledge_id": 1}])
    request = SimpleNamespace()

    monkeypatch.setattr(public_api, "authenticate_api_key", lambda request: {"key_type": "regular", "rate_remaining": 119})
    with pytest.raises(HTTPException, match="limit may not exceed 100"):
        public_api.read_knowledge_collection(request, 1, 101, 0, None, None, None)

    monkeypatch.setattr(public_api, "authenticate_api_key", lambda request: {"key_type": "master", "rate_remaining": None})
    result = public_api.read_knowledge_collection(request, 1, 1000, 0, None, None, None)
    assert result["key_type"] == "master"
    assert result["items"][0]["knowledge_id"] == 1
