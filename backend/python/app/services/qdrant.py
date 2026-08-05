from __future__ import annotations

from typing import Any, Sequence
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import HTTPException

from ..config import Settings, get_settings


_DISTANCE = {"cosine": "Cosine", "dot": "Dot", "euclid": "Euclid"}


class QdrantService:
    """Small Qdrant REST client for collection setup, search, and point writes."""

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        headers = {"api-key": self.settings.qdrant_api_key} if self.settings.qdrant_api_key else {}
        self._client = client or httpx.Client(
            base_url=self.settings.qdrant_url.rstrip("/"),
            headers=headers,
            timeout=30,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        if not self.settings.qdrant_enabled:
            raise HTTPException(status_code=503, detail="Qdrant is disabled")
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:2000]
            raise HTTPException(status_code=502, detail=f"Qdrant returned {exc.response.status_code}: {detail}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"Qdrant request failed: {exc}") from exc

    def collection_exists(self, collection: str | None = None) -> bool:
        if not self.settings.qdrant_enabled:
            return False
        name = quote(collection or self.settings.qdrant_collection, safe="")
        try:
            response = self._client.get(f"/collections/{name}")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Qdrant request failed: {exc}") from exc
        if response.status_code == 404:
            return False
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"Qdrant returned {response.status_code}: {response.text[:2000]}") from exc
        return True

    def ensure_collection(self) -> None:
        if not self.settings.qdrant_enabled:
            return
        collection = self.settings.qdrant_collection
        encoded = quote(collection, safe="")
        response = self._client.get(f"/collections/{encoded}")
        if response.status_code == 404:
            self._request(
                "PUT",
                f"/collections/{encoded}",
                json={
                    "vectors": {
                        "size": self.settings.qdrant_vector_size,
                        "distance": _DISTANCE[self.settings.qdrant_distance],
                        "on_disk": self.settings.qdrant_vectors_on_disk,
                    }
                },
            )
            existing_indexes: set[str] = set()
        else:
            try:
                response.raise_for_status()
                existing_indexes = set((response.json().get("result", {}).get("payload_schema") or {}).keys())
            except (httpx.HTTPError, ValueError) as exc:
                raise HTTPException(status_code=502, detail=f"Qdrant collection inspection failed: {exc}") from exc

        indexes = {
            "knowledge_id": "integer",
            "language_id": "integer",
            "section_id": "integer",
            "grimoire_id": "integer",
            "working_type": "keyword",
            "projection_type": "keyword",
            "direction": "keyword",
            "expected_target_types": "keyword",
            "field_ids": "integer",
            "is_active": "bool",
        }
        for field_name, field_schema in indexes.items():
            if field_name in existing_indexes:
                continue
            self._request(
                "PUT",
                f"/collections/{encoded}/index?wait=true",
                json={"field_name": field_name, "field_schema": field_schema},
            )

    def embed_query(self, text: str) -> list[float]:
        settings = self.settings
        if not settings.embedding_api_url or not settings.embedding_model:
            raise HTTPException(
                status_code=400,
                detail="Text search requires EMBEDDING_API_URL and EMBEDDING_MODEL; provide a raw vector instead",
            )
        headers = {"Content-Type": "application/json"}
        if settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {settings.embedding_api_key}"
        try:
            response = httpx.post(
                settings.embedding_api_url,
                headers=headers,
                json={"model": settings.embedding_model, "input": text},
                timeout=60,
            )
            response.raise_for_status()
            vector = response.json()["data"][0]["embedding"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=f"Embedding provider failed: {exc}") from exc
        if len(vector) != settings.qdrant_vector_size:
            raise HTTPException(
                status_code=502,
                detail=f"Embedding provider returned {len(vector)} dimensions; expected {settings.qdrant_vector_size}",
            )
        return [float(value) for value in vector]

    @staticmethod
    def _filter(filters: dict[str, str | int | bool]) -> dict[str, Any] | None:
        allowed = {
            "knowledge_id", "language_id", "section_id", "grimoire_id",
            "working_type", "projection_type", "direction",
            "expected_target_types", "field_ids", "is_active",
        }
        conditions = []
        for key, value in filters.items():
            if key not in allowed:
                raise HTTPException(status_code=400, detail=f"Unsupported Qdrant filter: {key}")
            conditions.append({"key": key, "match": {"value": value}})
        return {"must": conditions} if conditions else None

    def search(
        self,
        vector: Sequence[float],
        *,
        limit: int = 10,
        score_threshold: float | None = None,
        filters: dict[str, str | int | bool] | None = None,
    ) -> list[dict[str, Any]]:
        if len(vector) != self.settings.qdrant_vector_size:
            raise HTTPException(
                status_code=400,
                detail=f"Expected a {self.settings.qdrant_vector_size}-dimension vector, got {len(vector)}",
            )
        body: dict[str, Any] = {
            "query": list(vector),
            "filter": self._filter(filters or {}),
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }
        if score_threshold is not None:
            body["score_threshold"] = score_threshold
        name = quote(self.settings.qdrant_collection, safe="")
        response = self._request("POST", f"/collections/{name}/points/query", json=body)
        points = response.get("result", {}).get("points", [])
        return [
            {"id": str(point.get("id")), "score": point.get("score"), "payload": point.get("payload") or {}}
            for point in points
        ]

    def upsert(
        self,
        *,
        point_id: UUID | str,
        vector: Sequence[float],
        payload: dict[str, Any],
        collection: str | None = None,
    ) -> None:
        if len(vector) != self.settings.qdrant_vector_size:
            raise ValueError(f"Expected vector size {self.settings.qdrant_vector_size}, got {len(vector)}")
        name = quote(collection or self.settings.qdrant_collection, safe="")
        self._request(
            "PUT",
            f"/collections/{name}/points?wait=true",
            json={"points": [{"id": str(point_id), "vector": list(vector), "payload": payload}]},
        )


qdrant_service = QdrantService()
