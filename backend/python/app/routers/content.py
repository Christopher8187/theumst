from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request

from ..database import transaction
from ..dependencies import require_access
from ..schemas import BookDemoVisibility, BookPayload, MediaPostPayload


router = APIRouter(tags=["content"])


def _book_access(request: Request):
    return require_access(request, "books")


def _media_access(request: Request):
    return require_access(request, "media")


def _book_rows(cur):
    cur.execute(
        """
        SELECT
            g.grimoire_id,
            g.isbn,
            g.publish_date,
            g.version,
            g.source_key,
            COALESCE(lg.language_id, 1) AS language_id,
            COALESCE(lg.title, 'Untitled') AS title,
            COALESCE(lg.publisher, '') AS publisher,
            COALESCE(stats.section_count, 0) AS section_count,
            COALESCE(stats.knowledge_count, 0) AS knowledge_count,
            COALESCE(g.source_metadata->>'demo', 'false') = 'true' AS demo_enabled
        FROM grimoire g
        LEFT JOIN LATERAL (
            SELECT language_id, title, publisher
            FROM language_grimoire
            WHERE grimoire_id = g.grimoire_id
            ORDER BY (language_id = 1) DESC, language_id
            LIMIT 1
        ) lg ON true
        LEFT JOIN LATERAL (
            SELECT
                count(DISTINCT s.section_id) AS section_count,
                count(k.knowledge_id) AS knowledge_count
            FROM section s
            LEFT JOIN knowledge k ON k.section_id = s.section_id
            WHERE s.grimoire_id = g.grimoire_id
        ) stats ON true
        ORDER BY lower(COALESCE(lg.title, '')), g.grimoire_id DESC
        """
    )
    return list(cur.fetchall())


@router.get("/api/content/books")
def list_books(request: Request):
    _book_access(request)
    with transaction() as (_, cur):
        books = _book_rows(cur)
    return {"books": books}


@router.post("/api/content/books", status_code=201)
def create_book(payload: BookPayload, request: Request):
    _book_access(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            INSERT INTO grimoire (isbn, publish_date, version, source_key)
            VALUES (%s, %s, %s, NULLIF(%s, ''))
            RETURNING grimoire_id
            """,
            (payload.isbn, payload.publish_date, payload.version, payload.source_key),
        )
        grimoire_id = cur.fetchone()["grimoire_id"]
        cur.execute(
            """
            INSERT INTO language_grimoire
                (language_id, grimoire_id, title, is_original_language, publisher)
            VALUES (%s, %s, %s, true, %s)
            """,
            (payload.language_id, grimoire_id, payload.title.strip(), payload.publisher.strip()),
        )
    return {"ok": True, "grimoire_id": grimoire_id}


@router.put("/api/content/books/{grimoire_id}")
def update_book(grimoire_id: int, payload: BookPayload, request: Request):
    _book_access(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            UPDATE grimoire
            SET isbn = %s, publish_date = %s, version = %s, source_key = NULLIF(%s, '')
            WHERE grimoire_id = %s
            RETURNING grimoire_id
            """,
            (payload.isbn, payload.publish_date, payload.version, payload.source_key, grimoire_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Book not found")
        cur.execute(
            """
            INSERT INTO language_grimoire
                (language_id, grimoire_id, title, is_original_language, publisher)
            VALUES (%s, %s, %s, true, %s)
            ON CONFLICT (language_id, grimoire_id) DO UPDATE SET
                title = EXCLUDED.title,
                publisher = EXCLUDED.publisher
            """,
            (payload.language_id, grimoire_id, payload.title.strip(), payload.publisher.strip()),
        )
    return {"ok": True, "grimoire_id": grimoire_id}


@router.put("/api/content/books/{grimoire_id}/demo-visibility")
def set_book_demo_visibility(
    grimoire_id: int,
    payload: BookDemoVisibility,
    request: Request,
):
    _book_access(request)
    with transaction() as (_, cur):
        if payload.enabled:
            cur.execute(
                """
                SELECT
                    EXISTS (
                        SELECT 1 FROM grimoire WHERE grimoire_id = %s
                    ) AS book_exists,
                    EXISTS (
                        SELECT 1
                        FROM section s
                        JOIN knowledge k ON k.section_id = s.section_id
                        WHERE s.grimoire_id = %s AND k.is_active
                    ) AS has_knowledge
                """,
                (grimoire_id, grimoire_id),
            )
            readiness = cur.fetchone()
            if not readiness["book_exists"]:
                raise HTTPException(status_code=404, detail="Book not found")
            if not readiness["has_knowledge"]:
                raise HTTPException(
                    status_code=409,
                    detail="A book needs active knowledge objects before it can appear in the demo",
                )

        cur.execute(
            """
            UPDATE grimoire
            SET source_metadata = jsonb_set(
                COALESCE(source_metadata, '{}'::jsonb),
                '{demo}',
                to_jsonb(%s::boolean),
                true
            )
            WHERE grimoire_id = %s
            RETURNING grimoire_id,
                      COALESCE(source_metadata->>'demo', 'false') = 'true' AS demo_enabled
            """,
            (payload.enabled, grimoire_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Book not found")
    return {"ok": True, "book": row}


@router.delete("/api/content/books/{grimoire_id}")
def delete_book(grimoire_id: int, request: Request):
    _book_access(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT
                count(DISTINCT s.section_id) AS section_count,
                count(k.knowledge_id) AS knowledge_count
            FROM grimoire g
            LEFT JOIN section s ON s.grimoire_id = g.grimoire_id
            LEFT JOIN knowledge k ON k.section_id = s.section_id
            WHERE g.grimoire_id = %s
            """,
            (grimoire_id,),
        )
        counts = cur.fetchone()
        cur.execute("DELETE FROM grimoire WHERE grimoire_id = %s RETURNING grimoire_id", (grimoire_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Book not found")
    return {"ok": True, **counts}


def _slug_base(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:180] or "update"


def _unique_slug(cur, title: str, exclude_id: int | None = None) -> str:
    base = _slug_base(title)
    slug = base
    suffix = 2
    while True:
        cur.execute(
            """
            SELECT 1 FROM media_post
            WHERE slug = %s AND (%s::bigint IS NULL OR media_post_id <> %s)
            """,
            (slug, exclude_id, exclude_id),
        )
        if not cur.fetchone():
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def _list_media(cur, public_only: bool):
    where = "WHERE mp.status = 'published' AND mp.published_at <= now()" if public_only else ""
    cur.execute(
        f"""
        SELECT
            mp.media_post_id,
            mp.title,
            mp.slug,
            mp.excerpt,
            mp.body,
            mp.image_url,
            mp.status,
            mp.published_at,
            mp.created_at,
            mp.updated_at,
            mp.grimoire_id,
            u.username AS author
        FROM media_post mp
        LEFT JOIN "user" u ON u.user_id = mp.created_by_user_id
        {where}
        ORDER BY COALESCE(mp.published_at, mp.created_at) DESC, mp.media_post_id DESC
        """
    )
    return list(cur.fetchall())


@router.get("/api/news")
def public_news():
    with transaction() as (_, cur):
        posts = _list_media(cur, public_only=True)
    return {"posts": posts}


@router.get("/api/content/media")
def list_media(request: Request):
    _media_access(request)
    with transaction() as (_, cur):
        posts = _list_media(cur, public_only=False)
    return {"posts": posts}


@router.post("/api/content/media", status_code=201)
def create_media(payload: MediaPostPayload, request: Request):
    user = _media_access(request)
    with transaction() as (_, cur):
        slug = _unique_slug(cur, payload.title)
        cur.execute(
            """
            INSERT INTO media_post
                (created_by_user_id, grimoire_id, title, slug, excerpt, body, image_url, status, published_at)
            VALUES (%s, %s, %s, %s, %s, %s, NULLIF(%s, ''), %s,
                    CASE WHEN %s = 'published' THEN now() ELSE NULL END)
            RETURNING media_post_id, slug
            """,
            (
                user["user_id"], payload.grimoire_id, payload.title.strip(), slug, payload.excerpt.strip(),
                payload.body.strip(), payload.image_url, payload.status, payload.status,
            ),
        )
        row = cur.fetchone()
    return {"ok": True, **row}


@router.put("/api/content/media/{media_post_id}")
def update_media(media_post_id: int, payload: MediaPostPayload, request: Request):
    _media_access(request)
    with transaction() as (_, cur):
        slug = _unique_slug(cur, payload.title, exclude_id=media_post_id)
        cur.execute(
            """
            UPDATE media_post SET
                title = %s,
                slug = %s,
                excerpt = %s,
                body = %s,
                image_url = NULLIF(%s, ''),
                grimoire_id = %s,
                status = %s,
                published_at = CASE
                    WHEN %s = 'published' THEN COALESCE(published_at, now())
                    ELSE NULL
                END
            WHERE media_post_id = %s
            RETURNING media_post_id, slug
            """,
            (
                payload.title.strip(), slug, payload.excerpt.strip(), payload.body.strip(),
                payload.image_url, payload.grimoire_id,
                payload.status, payload.status, media_post_id,
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
    return {"ok": True, **row}


@router.delete("/api/content/media/{media_post_id}")
def delete_media(media_post_id: int, request: Request):
    _media_access(request)
    with transaction() as (_, cur):
        cur.execute(
            "DELETE FROM media_post WHERE media_post_id = %s RETURNING media_post_id",
            (media_post_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Post not found")
    return {"ok": True}
