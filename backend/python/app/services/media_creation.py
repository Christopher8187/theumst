"""Replay a completed editorial create without creating another post or email."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from fastapi import HTTPException

from ..schemas import MediaPostPayload


def _fingerprint(payload: MediaPostPayload) -> str:
    data = payload.model_dump(mode="json", exclude={"request_id"})
    # Match the values persisted by content.py, including optional/default fields.
    for field in ("title", "excerpt", "body", "email_introduction"):
        data[field] = data[field].strip()
    data["image_url"] = data["image_url"] or None
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def create_media_once(cur, *, user_id: int, payload: MediaPostPayload, create: Callable[[], dict]) -> dict:
    """Caller owns one transaction covering request identity and all publication writes."""
    if payload.request_id is None:
        if payload.announce:
            raise HTTPException(status_code=422, detail="A request_id UUID is required when creating an announcement")
        return create()  # Preserve existing news-only callers.

    request_id = str(payload.request_id)
    fingerprint = _fingerprint(payload)
    # The lock exists before any request row, so concurrent first attempts cannot
    # both create. Collisions only serialize unrelated requests, never equate them.
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"media-create/{user_id}/{request_id}",))
    cur.execute(
        "SELECT payload_sha256, response FROM media_create_request WHERE user_id = %s AND request_id = %s",
        (user_id, request_id),
    )
    previous = cur.fetchone()
    if previous:
        if previous["payload_sha256"] != fingerprint:
            raise HTTPException(
                status_code=409,
                detail="This request already created a post with different content. Refresh Media and edit the saved post.",
            )
        return previous["response"]

    response = create()
    cur.execute(
        "INSERT INTO media_create_request (user_id, request_id, payload_sha256, response) VALUES (%s, %s, %s, %s::jsonb)",
        (user_id, request_id, fingerprint, json.dumps(response)),
    )
    return response
