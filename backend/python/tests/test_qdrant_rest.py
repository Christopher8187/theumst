from dataclasses import replace
import json

import httpx

from app.config import get_settings
from app.services.qdrant import QdrantService


def test_qdrant_collection_search_and_upsert_use_rest_contract():
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, dict(request.headers), body))
        if request.method == "GET" and request.url.path.endswith("/collections/test-collection"):
            return httpx.Response(404, json={"status": {"error": "missing"}})
        if request.method == "POST" and request.url.path.endswith("/points/query"):
            return httpx.Response(200, json={
                "status": "ok",
                "result": {"points": [{"id": "abc", "score": 0.91, "payload": {"knowledge_id": 4}}]},
            })
        return httpx.Response(200, json={"status": "ok", "result": {}})

    settings = replace(
        get_settings(),
        qdrant_enabled=True,
        qdrant_url="http://qdrant.test",
        qdrant_api_key="secret",
        qdrant_collection="test-collection",
        qdrant_vector_size=3,
        qdrant_distance="cosine",
    )
    client = httpx.Client(
        base_url=settings.qdrant_url,
        headers={"api-key": settings.qdrant_api_key},
        transport=httpx.MockTransport(handler),
    )
    service = QdrantService(settings, client)

    service.ensure_collection()
    results = service.search([0.1, 0.2, 0.3], filters={"working_type": "theorem"})
    service.upsert(point_id="00000000-0000-0000-0000-000000000001", vector=[0.1, 0.2, 0.3], payload={"knowledge_id": 4})

    assert results[0]["payload"]["knowledge_id"] == 4
    create = next(item for item in seen if item[0] == "PUT" and item[1].endswith("/collections/test-collection"))
    assert create[3]["vectors"] == {"size": 3, "distance": "Cosine", "on_disk": False}
    query = next(item for item in seen if item[1].endswith("/points/query"))
    assert query[3]["filter"]["must"][0]["key"] == "working_type"
    assert query[2]["api-key"] == "secret"
    upsert = next(item for item in seen if item[1].endswith("/points"))
    assert upsert[3]["points"][0]["id"].endswith("0001")
