from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated, Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ..config import get_settings
from ..database import transaction
from ..dependencies import require_access, require_role, require_user
from ..schemas import (
    DemoAccessRequestPayload,
    DemoNotePayload,
    DemoProgressPayload,
    DemoReviewPayload,
    DemoStudyStatePayload,
)
from ..services.qdrant import qdrant_service
from ..services.graph_sidecar import GRAPH_ROLES, fetch_contents, fetch_focused_graph


router = APIRouter(prefix="/api/demo", tags=["web-demo"])
REVIEW_ROLES = {"admin", "superadmin"}
DEMO_VERSION = "0.1.0"
SIMILAR_MAX_K = 25
SIMILAR_QUERY_OVERFETCH = 4
GRAPH_MAX_NODES = 150
GRAPH_MAX_DEPTH = 2
GRAPH_CACHE_SECONDS = 300


def _governed_image_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer validated application image routes when a stored key is available."""
    governed: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        storage_key = row.pop("storage_key", None)
        if storage_key:
            row["url"] = f"/api/v1/storage/{quote(str(storage_key), safe='/')}"
        governed.append(row)
    return governed


def _public_account_type(authority_type: str) -> str:
    if authority_type in {"user", "betatester", "manager"}:
        return authority_type
    return "staff"


def _demo_user(request: Request) -> dict[str, Any]:
    return require_access(request, "demo")


def _reviewer(request: Request) -> dict[str, Any]:
    return require_role(request, REVIEW_ROLES)


def _access_payload(user: dict[str, Any], access_request: dict[str, Any] | None) -> dict[str, Any]:
    access_points = set(user.get("access_points") or [])
    return {
        "version": DEMO_VERSION,
        "account_type": _public_account_type(user["authority_type"]),
        "can_enter": "demo" in access_points,
        "can_review": user["authority_type"] in REVIEW_ROLES,
        "request": access_request,
    }


@router.get("/access")
def demo_access(request: Request):
    user = require_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT status, request_message, review_note, requested_at, reviewed_at
            FROM demo_access_request
            WHERE user_id = %s
            """,
            (user["user_id"],),
        )
        access_request = cur.fetchone()
    return _access_payload(user, access_request)


@router.get("/auth-check", status_code=204)
def demo_auth_check(request: Request):
    _demo_user(request)
    return Response(status_code=204)


@router.post("/access/request")
def request_demo_access(payload: DemoAccessRequestPayload, request: Request):
    user = require_user(request)
    if "demo" in set(user.get("access_points") or []):
        return {"ok": True, "already_authorized": True}

    with transaction() as (_, cur):
        cur.execute(
            """
            INSERT INTO demo_access_request
                (user_id, status, request_message, review_note, requested_at,
                 reviewed_by_user_id, reviewed_at)
            VALUES (%s, 'pending', %s, '', now(), NULL, NULL)
            ON CONFLICT (user_id) DO UPDATE SET
                status = 'pending',
                request_message = EXCLUDED.request_message,
                review_note = '',
                requested_at = now(),
                reviewed_by_user_id = NULL,
                reviewed_at = NULL
            RETURNING status, request_message, requested_at
            """,
            (user["user_id"], payload.message.strip()),
        )
        row = cur.fetchone()
    return {"ok": True, "request": row}


@router.get("/access/requests")
def list_demo_requests(request: Request):
    _reviewer(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT r.user_id, u.username, u.email,
                   CASE a.name
                       WHEN 'user' THEN 'user'
                       WHEN 'betatester' THEN 'betatester'
                       WHEN 'manager' THEN 'manager'
                       ELSE 'staff'
                   END AS account_type,
                   r.status, r.request_message, r.review_note,
                   r.requested_at, r.reviewed_at,
                   reviewer.username AS reviewed_by
            FROM demo_access_request r
            JOIN "user" u ON u.user_id = r.user_id
            JOIN authority a ON a.authority_id = u.authority_id
            LEFT JOIN "user" reviewer ON reviewer.user_id = r.reviewed_by_user_id
            ORDER BY
                CASE r.status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
                r.requested_at DESC
            """
        )
        rows = list(cur.fetchall())
    return {"requests": rows}


def _review_request(user_id: int, payload: DemoReviewPayload, request: Request, status: str):
    reviewer = _reviewer(request)
    with transaction() as (_, cur):
        cur.execute(
            "SELECT status FROM demo_access_request WHERE user_id = %s FOR UPDATE",
            (user_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Demo access request not found")

        if status == "approved":
            cur.execute(
                """
                UPDATE "user" SET authority_id = (
                    SELECT authority_id FROM authority WHERE name = 'betatester'
                )
                WHERE user_id = %s
                  AND authority_id IN (
                      SELECT authority_id FROM authority WHERE name IN ('user', 'betatester')
                  )
                """,
                (user_id,),
            )

        cur.execute(
            """
            UPDATE demo_access_request SET
                status = %s,
                review_note = %s,
                reviewed_by_user_id = %s,
                reviewed_at = now()
            WHERE user_id = %s
            RETURNING status, review_note, reviewed_at
            """,
            (status, payload.note.strip(), reviewer["user_id"], user_id),
        )
        row = cur.fetchone()
    return {"ok": True, "request": row}


@router.post("/access/requests/{user_id}/approve")
def approve_demo_request(user_id: int, payload: DemoReviewPayload, request: Request):
    return _review_request(user_id, payload, request, "approved")


@router.post("/access/requests/{user_id}/reject")
def reject_demo_request(user_id: int, payload: DemoReviewPayload, request: Request):
    return _review_request(user_id, payload, request, "rejected")


def _book_rows(cur, user_id: int, query: str = "") -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT g.grimoire_id, g.isbn, g.version, g.source_key,
               g.source_metadata->>'summary' AS summary,
               lg.title, lg.publisher,
               (ug.user_id IS NOT NULL) AS summoned,
               ug.summoned_at, ug.last_opened_at,
               count(DISTINCT s.section_id) AS section_count,
               count(DISTINCT k.knowledge_id) AS knowledge_count,
               count(DISTINCT p.knowledge_id) FILTER (WHERE p.completed) AS completed_count
        FROM grimoire g
        JOIN language_grimoire lg
          ON lg.grimoire_id = g.grimoire_id AND lg.language_id = 1
        LEFT JOIN user_grimoire ug
          ON ug.grimoire_id = g.grimoire_id AND ug.user_id = %s
        LEFT JOIN section s ON s.grimoire_id = g.grimoire_id
        LEFT JOIN knowledge k ON k.section_id = s.section_id
        LEFT JOIN demo_knowledge_progress p
          ON p.knowledge_id = k.knowledge_id AND p.user_id = %s
        WHERE COALESCE(g.source_metadata->>'demo', 'false') = 'true'
          AND (%s = '' OR lower(lg.title) LIKE '%%' || lower(%s) || '%%')
        GROUP BY g.grimoire_id, lg.title, lg.publisher, ug.user_id,
                 ug.summoned_at, ug.last_opened_at
        ORDER BY COALESCE(ug.last_opened_at, 'epoch'::timestamptz) DESC,
                 lower(lg.title)
        """,
        (user_id, user_id, query, query),
    )
    return list(cur.fetchall())


@router.get("/books")
def list_demo_books(request: Request, q: str = ""):
    user = _demo_user(request)
    with transaction() as (_, cur):
        books = _book_rows(cur, user["user_id"], q.strip()[:200])
    return {"books": books}


@router.get("/books/{grimoire_id}")
def get_demo_book(grimoire_id: int, request: Request):
    user = _demo_user(request)
    with transaction() as (_, cur):
        books = [row for row in _book_rows(cur, user["user_id"]) if row["grimoire_id"] == grimoire_id]
        if not books:
            raise HTTPException(status_code=404, detail="Demo book not found")
        cur.execute(
            """
            SELECT s.section_id, s.parent_section, s.section_number, ls.section_name
            FROM section s
            LEFT JOIN language_section ls
              ON ls.section_id = s.section_id AND ls.language_id = 1
            WHERE s.grimoire_id = %s
            ORDER BY COALESCE((s.source_metadata->>'demo_order')::int, s.section_id)
            """,
            (grimoire_id,),
        )
        sections = list(cur.fetchall())
        contents_tree = fetch_contents(cur, grimoire_id=grimoire_id)
    return {"book": books[0], "contents": sections, "contents_tree": contents_tree}


def _graph_include_roles(value: str) -> tuple[str, ...]:
    roles = tuple(sorted({role.strip().lower() for role in value.split(",") if role.strip()}))
    unsupported = set(roles) - (GRAPH_ROLES - {"backbone"})
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail="include contains an unsupported learning role",
        )
    return roles


def _graph_cache_headers(etag: str) -> dict[str, str]:
    return {
        "ETag": etag,
        "Cache-Control": f"private, max-age={GRAPH_CACHE_SECONDS}",
        "Vary": "Authorization, Cookie, Accept-Encoding",
    }


@router.get("/grimoires/{grimoire_id}/graph")
def get_grimoire_graph(
    grimoire_id: int,
    request: Request,
    response: Response,
    focus: str,
    ancestor_depth: Annotated[int, Query(ge=0, le=GRAPH_MAX_DEPTH)] = 2,
    descendant_depth: Annotated[int, Query(ge=0, le=GRAPH_MAX_DEPTH)] = 2,
    include: str = "support,assessment",
    limit: Annotated[int, Query(ge=1, le=GRAPH_MAX_NODES)] = GRAPH_MAX_NODES,
):
    """Return one bounded book-order learning map around the requested item."""
    _demo_user(request)
    if not isinstance(ancestor_depth, int) or not 0 <= ancestor_depth <= GRAPH_MAX_DEPTH:
        raise HTTPException(status_code=422, detail=f"ancestor_depth must be between 0 and {GRAPH_MAX_DEPTH}")
    if not isinstance(descendant_depth, int) or not 0 <= descendant_depth <= GRAPH_MAX_DEPTH:
        raise HTTPException(status_code=422, detail=f"descendant_depth must be between 0 and {GRAPH_MAX_DEPTH}")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= GRAPH_MAX_NODES:
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {GRAPH_MAX_NODES}")
    include_roles = _graph_include_roles(include)

    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT 1
            FROM grimoire
            WHERE grimoire_id = %s
              AND source_metadata->>'demo' = 'true'
            """,
            (grimoire_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Book not found")
        try:
            graph = fetch_focused_graph(
                cur,
                grimoire_id=grimoire_id,
                focus=focus,
                ancestor_depth=ancestor_depth,
                descendant_depth=descendant_depth,
                include_roles=include_roles,
                limit=limit,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Learning item not found in this book") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    canonical = json.dumps(graph, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    etag = f'"{hashlib.sha256(canonical).hexdigest()}"'
    headers = _graph_cache_headers(etag)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    for name, value in headers.items():
        response.headers[name] = value
    return graph


@router.post("/grimoires/{grimoire_id}/summon")
def summon_grimoire(grimoire_id: int, request: Request):
    user = _demo_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT 1 FROM grimoire
            WHERE grimoire_id = %s
              AND COALESCE(source_metadata->>'demo', 'false') = 'true'
            """,
            (grimoire_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Demo book not found")
        cur.execute(
            """
            INSERT INTO user_grimoire (user_id, grimoire_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, grimoire_id) DO UPDATE SET last_opened_at = now()
            RETURNING summoned_at, last_opened_at
            """,
            (user["user_id"], grimoire_id),
        )
        row = cur.fetchone()
    return {"ok": True, "grimoire": row}


@router.get("/grimoires")
def list_grimoires(request: Request, q: str = ""):
    user = _demo_user(request)
    with transaction() as (_, cur):
        books = [
            row for row in _book_rows(cur, user["user_id"], q.strip()[:200])
            if row["summoned"]
        ]
    return {"grimoires": books}


def _breadcrumbs(sections: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    by_id = {row["section_id"]: row for row in sections}
    result: dict[int, list[dict[str, Any]]] = {}
    for section in sections:
        chain = []
        current = section
        seen = set()
        while current and current["section_id"] not in seen:
            seen.add(current["section_id"])
            chain.append({
                "section_id": current["section_id"],
                "number": current["section_number"],
                "name": current.get("section_name") or current["section_number"],
            })
            current = by_id.get(current.get("parent_section"))
        result[section["section_id"]] = list(reversed(chain))
    return result


@router.get("/grimoires/{grimoire_id}/knowledge")
def get_grimoire_knowledge(grimoire_id: int, request: Request):
    user = _demo_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT g.grimoire_id, lg.title
            FROM grimoire g
            JOIN language_grimoire lg
              ON lg.grimoire_id = g.grimoire_id AND lg.language_id = 1
            WHERE g.grimoire_id = %s
              AND COALESCE(g.source_metadata->>'demo', 'false') = 'true'
            """,
            (grimoire_id,),
        )
        book = cur.fetchone()
        if not book:
            raise HTTPException(status_code=404, detail="Demo grimoire not found")

        cur.execute(
            """
            INSERT INTO user_grimoire (user_id, grimoire_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, grimoire_id) DO UPDATE SET last_opened_at = now()
            """,
            (user["user_id"], grimoire_id),
        )
        cur.execute(
            """
            SELECT s.section_id, s.parent_section, s.section_number, ls.section_name
            FROM section s
            LEFT JOIN language_section ls
              ON ls.section_id = s.section_id AND ls.language_id = 1
            WHERE s.grimoire_id = %s
            ORDER BY COALESCE((s.source_metadata->>'demo_order')::int, s.section_id)
            """,
            (grimoire_id,),
        )
        sections = list(cur.fetchall())
        section_paths = _breadcrumbs(sections)

        cur.execute(
            """
            SELECT k.knowledge_id, k.section_id, k.type, k.source_key,
                   k.source_metadata->'order' AS source_order,
                   lk.label,
                   COALESCE(p.completed, false) AS completed
            FROM knowledge k
            JOIN section s ON s.section_id = k.section_id
            JOIN language_knowledge lk
              ON lk.knowledge_id = k.knowledge_id AND lk.language_id = 1
            LEFT JOIN demo_knowledge_progress p
              ON p.knowledge_id = k.knowledge_id AND p.user_id = %s
            WHERE s.grimoire_id = %s AND k.is_active
            ORDER BY COALESCE((k.source_metadata->>'demo_order')::int, 2147483647),
                     k.source_metadata->'order' NULLS LAST,
                     k.knowledge_id
            """,
            (user["user_id"], grimoire_id),
        )
        nodes = list(cur.fetchall())
        node_ids = [row["knowledge_id"] for row in nodes]
        for row in nodes:
            row["breadcrumbs"] = section_paths.get(row["section_id"], [])

        relation_counts: dict[int, int] = {}
        if node_ids:
            cur.execute(
                """
                SELECT knowledge_id, count(*) AS relation_count
                FROM (
                    SELECT from_id AS knowledge_id
                    FROM relation
                    WHERE from_id = ANY(%s) AND to_id = ANY(%s)
                    UNION ALL
                    SELECT to_id AS knowledge_id
                    FROM relation
                    WHERE from_id = ANY(%s) AND to_id = ANY(%s)
                ) endpoints
                GROUP BY knowledge_id
                """,
                (node_ids, node_ids, node_ids, node_ids),
            )
            relation_counts = {
                int(row["knowledge_id"]): int(row["relation_count"])
                for row in cur.fetchall()
            }

        cur.execute(
            """
            SELECT current_knowledge_id, questions_knowledge_id, updated_at
            FROM demo_study_state
            WHERE user_id = %s AND grimoire_id = %s
            """,
            (user["user_id"], grimoire_id),
        )
        state = cur.fetchone()

    return {
        "book": book,
        "sections": sections,
        "knowledge": nodes,
        "relation_counts": relation_counts,
        "current_knowledge_id": state["current_knowledge_id"] if state else None,
        "questions_knowledge_id": state["questions_knowledge_id"] if state else None,
    }


@router.get("/grimoires/{grimoire_id}/knowledge/{knowledge_id}")
def get_grimoire_knowledge_detail(grimoire_id: int, knowledge_id: int, request: Request):
    user = _demo_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT k.knowledge_id, k.section_id, k.type, k.source_key,
                   k.source_metadata->'order' AS source_order,
                   lk.label, lk.statement, lk.working, lk.working_summary,
                   COALESCE(p.completed, false) AS completed
            FROM knowledge k
            JOIN section s ON s.section_id = k.section_id
            JOIN grimoire g ON g.grimoire_id = s.grimoire_id
            JOIN language_knowledge lk
              ON lk.knowledge_id = k.knowledge_id AND lk.language_id = 1
            LEFT JOIN demo_knowledge_progress p
              ON p.knowledge_id = k.knowledge_id AND p.user_id = %s
            WHERE s.grimoire_id = %s
              AND k.knowledge_id = %s
              AND k.is_active
              AND COALESCE(g.source_metadata->>'demo', 'false') = 'true'
            """,
            (user["user_id"], grimoire_id, knowledge_id),
        )
        node = cur.fetchone()
        if not node:
            raise HTTPException(status_code=404, detail="Demo knowledge object not found")
        cur.execute(
            """
            SELECT source_image_id, semantic_context_name, storage_key, url, metadata
            FROM book_image
            WHERE knowledge_id = %s AND is_active
            ORDER BY book_image_id
            """,
            (knowledge_id,),
        )
        node["images"] = _governed_image_rows(list(cur.fetchall()))
    return {"knowledge": node}


@router.put("/progress/{knowledge_id}")
def update_progress(
    knowledge_id: int,
    payload: DemoProgressPayload,
    request: Request,
):
    user = _demo_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT k.knowledge_id
            FROM knowledge k
            JOIN section s ON s.section_id = k.section_id
            JOIN user_grimoire ug ON ug.grimoire_id = s.grimoire_id
            WHERE k.knowledge_id = %s AND ug.user_id = %s
            """,
            (knowledge_id, user["user_id"]),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Knowledge object not found")
        cur.execute(
            """
            INSERT INTO demo_knowledge_progress
                (user_id, knowledge_id, completed, completed_at)
            VALUES (%s, %s, %s, CASE WHEN %s THEN now() ELSE NULL END)
            ON CONFLICT (user_id, knowledge_id) DO UPDATE SET
                completed = EXCLUDED.completed,
                completed_at = CASE WHEN EXCLUDED.completed THEN now() ELSE NULL END
            RETURNING completed, completed_at
            """,
            (user["user_id"], knowledge_id, payload.completed, payload.completed),
        )
        row = cur.fetchone()
    return {"ok": True, "progress": row}


@router.put("/grimoires/{grimoire_id}/state")
def update_study_state(
    grimoire_id: int,
    payload: DemoStudyStatePayload,
    request: Request,
):
    user = _demo_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT 1
            FROM knowledge k JOIN section s ON s.section_id = k.section_id
            WHERE k.knowledge_id = %s AND s.grimoire_id = %s
            """,
            (payload.knowledge_id, grimoire_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Knowledge object is not in this grimoire")
        cur.execute(
            """
            INSERT INTO demo_study_state (user_id, grimoire_id, current_knowledge_id, questions_knowledge_id)
            VALUES (%s, %s, CASE WHEN %s='text' THEN %s END, CASE WHEN %s='questions' THEN %s END)
            ON CONFLICT (user_id, grimoire_id) DO UPDATE SET
                current_knowledge_id = CASE WHEN %s='text' THEN EXCLUDED.current_knowledge_id ELSE demo_study_state.current_knowledge_id END,
                questions_knowledge_id = CASE WHEN %s='questions' THEN EXCLUDED.questions_knowledge_id ELSE demo_study_state.questions_knowledge_id END
            """,
            (user["user_id"], grimoire_id, payload.realm, payload.knowledge_id, payload.realm, payload.knowledge_id, payload.realm, payload.realm),
        )
    return {"ok": True}


@router.get("/notes")
def list_notes(
    request: Request,
    grimoire_id: int | None = None,
    knowledge_id: int | None = None,
):
    user = _demo_user(request)
    clauses = ["n.user_id = %s"]
    values: list[Any] = [user["user_id"]]
    if grimoire_id is not None:
        clauses.append("n.grimoire_id = %s")
        values.append(grimoire_id)
    if knowledge_id is not None:
        clauses.append("n.knowledge_id = %s")
        values.append(knowledge_id)
    with transaction() as (_, cur):
        cur.execute(
            f"""
            SELECT n.demo_note_id, n.grimoire_id, n.knowledge_id, n.note_type,
                   n.tag, n.content, n.created_at, n.updated_at,
                   CASE WHEN g.source_metadata->>'demo'='true' AND COALESCE(k.is_active,true) THEN lk.label END AS knowledge_label,
                   CASE WHEN g.source_metadata->>'demo'='true' THEN lg.title END AS book_title,
                   COALESCE(g.source_metadata->>'demo'='true' AND COALESCE(k.is_active,true),false) AS source_available
            FROM demo_note n
            LEFT JOIN grimoire g ON g.grimoire_id=n.grimoire_id
            LEFT JOIN knowledge k ON k.knowledge_id=n.knowledge_id
            LEFT JOIN language_knowledge lk
              ON lk.knowledge_id = n.knowledge_id AND lk.language_id = 1
            LEFT JOIN language_grimoire lg
              ON lg.grimoire_id = n.grimoire_id AND lg.language_id = 1
            WHERE {' AND '.join(clauses)}
            ORDER BY n.updated_at DESC, n.demo_note_id DESC
            """,
            tuple(values),
        )
        rows = list(cur.fetchall())
    return {"notes": rows}


@router.post("/notes", status_code=201)
def create_note(payload: DemoNotePayload, request: Request):
    user = _demo_user(request)
    with transaction() as (_, cur):
        if payload.knowledge_id is not None:
            cur.execute(
                """
                SELECT s.grimoire_id
                FROM knowledge k
                JOIN section s ON s.section_id = k.section_id
                JOIN user_grimoire ug
                  ON ug.grimoire_id = s.grimoire_id AND ug.user_id = %s
                WHERE k.knowledge_id = %s
                  AND (%s::int IS NULL OR s.grimoire_id = %s)
                """,
                (
                    user["user_id"], payload.knowledge_id,
                    payload.grimoire_id, payload.grimoire_id,
                ),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Knowledge note target not found")
        cur.execute(
            """
            INSERT INTO demo_note
                (user_id, grimoire_id, knowledge_id, note_type, tag, content)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING demo_note_id, created_at, updated_at
            """,
            (
                user["user_id"], payload.grimoire_id, payload.knowledge_id,
                payload.note_type, payload.tag.strip(), payload.content,
            ),
        )
        row = cur.fetchone()
    return {"ok": True, "note": row}


@router.put("/notes/{note_id}")
def update_note(note_id: int, payload: DemoNotePayload, request: Request):
    user = _demo_user(request)
    with transaction() as (_, cur):
        if payload.knowledge_id is not None:
            cur.execute(
                """
                SELECT s.grimoire_id
                FROM knowledge k
                JOIN section s ON s.section_id = k.section_id
                JOIN user_grimoire ug
                  ON ug.grimoire_id = s.grimoire_id AND ug.user_id = %s
                WHERE k.knowledge_id = %s
                  AND (%s::int IS NULL OR s.grimoire_id = %s)
                """,
                (
                    user["user_id"], payload.knowledge_id,
                    payload.grimoire_id, payload.grimoire_id,
                ),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Knowledge note target not found")
        cur.execute(
            """
            UPDATE demo_note SET
                grimoire_id = %s,
                knowledge_id = %s,
                note_type = %s,
                tag = %s,
                content = %s
            WHERE demo_note_id = %s AND user_id = %s
            RETURNING demo_note_id, updated_at
            """,
            (
                payload.grimoire_id, payload.knowledge_id, payload.note_type,
                payload.tag.strip(), payload.content, note_id, user["user_id"],
            ),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True, "note": row}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, request: Request):
    user = _demo_user(request)
    with transaction() as (_, cur):
        cur.execute(
            "DELETE FROM demo_note WHERE demo_note_id = %s AND user_id = %s RETURNING demo_note_id",
            (note_id, user["user_id"]),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


def _projection_preference(row: dict[str, Any], configured: tuple[str, ...]) -> tuple[int, str, str]:
    key = f"{row['projection_type']}:{row['direction']}"
    try:
        rank = configured.index(key)
    except ValueError:
        rank = len(configured)
    return rank, str(row["qdrant_collection"]), str(row["embedding_id"])


def _select_source_embedding(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    settings = get_settings()
    configured = settings.demo_similarity_projections
    usable = [
        row for row in rows
        if f"{row.get('projection_type')}:{row.get('direction')}" in configured
        and row.get("distance_metric") == "cosine"
        and isinstance(row.get("vector_size"), int)
        and row["vector_size"] > 0
        and row.get("qdrant_collection")
        and row.get("embedding_id")
    ]
    if not usable:
        return None
    return min(
        usable,
        key=lambda row: (
            _projection_preference(row, configured)[0],
            row["qdrant_collection"] != settings.qdrant_collection,
            int(row["embedding_model_id"]),
            str(row["embedding_id"]),
        ),
    )


def _point_scores(hits: list[dict[str, Any]], source_point_id: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for hit in hits:
        point_id = str(hit.get("id") or "")
        try:
            point_id = str(UUID(point_id))
        except (ValueError, TypeError, AttributeError):
            continue
        if point_id == source_point_id:
            continue
        score = hit.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            continue
        score = float(score)
        if not math.isfinite(score):
            continue
        previous = scores.get(point_id)
        if previous is None or score > previous:
            scores[point_id] = score
    return scores


def _embedding_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("embedding_model_id"),
        row.get("provider"),
        row.get("model_name"),
        row.get("model_revision"),
        row.get("vector_size"),
        row.get("distance_metric"),
        row.get("qdrant_collection"),
        row.get("projection_type"),
        row.get("direction"),
        row.get("language_id"),
    )


def _similar_results(
    rows: list[dict[str, Any]],
    *,
    source: dict[str, Any],
    scores: dict[str, float],
    k: int,
) -> list[dict[str, Any]]:
    source_signature = _embedding_signature(source)
    best_by_knowledge: dict[int, tuple[float, str, dict[str, Any]]] = {}
    for row in rows:
        point_id = str(row.get("embedding_id") or "")
        score = scores.get(point_id)
        if score is None or _embedding_signature(row) != source_signature:
            continue
        knowledge_id = int(row["knowledge_id"])
        if knowledge_id == int(source["knowledge_id"]):
            continue
        previous = best_by_knowledge.get(knowledge_id)
        candidate = (score, point_id, row)
        if previous is None or (-score, point_id) < (-previous[0], previous[1]):
            best_by_knowledge[knowledge_id] = candidate

    ordered = sorted(
        best_by_knowledge.values(),
        key=lambda item: (-item[0], int(item[2]["knowledge_id"]), item[1]),
    )[:k]
    return [
        {
            "knowledge_id": int(row["knowledge_id"]),
            "grimoire_id": int(row["grimoire_id"]),
            "book_title": row["book_title"],
            "label": row["label"],
            "statement": row["statement"],
            "similarity_score": score,
        }
        for score, _, row in ordered
    ]


@router.get("/knowledge/{knowledge_id}/similar")
def find_similar_knowledge(
    knowledge_id: int,
    request: Request,
    k: Annotated[int, Query(ge=1, le=SIMILAR_MAX_K)] = 10,
    scope: Literal["book"] = "book",
):
    _demo_user(request)
    if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= SIMILAR_MAX_K:
        raise HTTPException(status_code=422, detail=f"k must be between 1 and {SIMILAR_MAX_K}")
    if scope != "book":
        raise HTTPException(status_code=422, detail="scope must be 'book'")

    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT k.knowledge_id, s.grimoire_id
            FROM knowledge k
            JOIN section s ON s.section_id = k.section_id
            JOIN grimoire g ON g.grimoire_id = s.grimoire_id
            WHERE k.knowledge_id = %s
              AND k.is_active
              AND g.source_metadata->>'demo' = 'true'
            """,
            (knowledge_id,),
        )
        source_knowledge = cur.fetchone()
        if not source_knowledge:
            raise HTTPException(status_code=404, detail="Knowledge object not found")
        cur.execute(
            """
            SELECT e.embedding_id::text AS embedding_id,
                   e.embedding_model_id,
                   sp.knowledge_id, sp.language_id,
                   sp.projection_type, sp.direction,
                   em.provider, em.model_name, em.model_revision,
                   em.vector_size, em.distance_metric, em.qdrant_collection
            FROM semantic_projection sp
            JOIN embedding e
              ON e.semantic_projection_id = sp.semantic_projection_id
             AND e.status = 'indexed'
            JOIN embedding_model em
              ON em.embedding_model_id = e.embedding_model_id
             AND em.is_active
            WHERE sp.knowledge_id = %s
              AND sp.is_active
              AND em.distance_metric = 'cosine'
            ORDER BY sp.projection_type, sp.direction,
                     em.embedding_model_id, e.embedding_id
            """,
            (knowledge_id,),
        )
        source = _select_source_embedding(list(cur.fetchall()))

    if source is None:
        raise HTTPException(
            status_code=409,
            detail="Similar suggestions are unavailable for this item.",
        )
    source["grimoire_id"] = int(source_knowledge["grimoire_id"])
    source_point_id = str(UUID(str(source["embedding_id"])))
    overfetch = min(128, max(k + 1, (k * SIMILAR_QUERY_OVERFETCH) + 1))
    try:
        hits = qdrant_service.query_by_point(
            collection=str(source["qdrant_collection"]),
            point_id=source_point_id,
            limit=overfetch,
            filters={
                "grimoire_id": int(source["grimoire_id"]),
                "language_id": int(source["language_id"]),
                "projection_type": str(source["projection_type"]),
                "direction": str(source["direction"]),
                "is_active": True,
            },
        )
    except HTTPException as exc:
        raise HTTPException(
            status_code=503,
            detail="Similar suggestions are temporarily unavailable.",
        ) from exc
    scores = _point_scores(hits, source_point_id)
    candidate_rows: list[dict[str, Any]] = []
    if scores:
        with transaction() as (_, cur):
            cur.execute(
                """
                SELECT e.embedding_id::text AS embedding_id,
                       e.embedding_model_id,
                       target.knowledge_id, target_sp.language_id,
                       target_sp.projection_type, target_sp.direction,
                       target_section.grimoire_id,
                       target_book.title AS book_title,
                       target_lk.label, target_lk.statement,
                       em.provider, em.model_name, em.model_revision,
                       em.vector_size, em.distance_metric, em.qdrant_collection
                FROM embedding e
                JOIN embedding_model em
                  ON em.embedding_model_id = e.embedding_model_id
                 AND em.is_active
                JOIN semantic_projection target_sp
                  ON target_sp.semantic_projection_id = e.semantic_projection_id
                 AND target_sp.is_active
                JOIN knowledge target
                  ON target.knowledge_id = target_sp.knowledge_id
                 AND target.is_active
                JOIN language_knowledge target_lk
                  ON target_lk.knowledge_id = target.knowledge_id
                 AND target_lk.language_id = target_sp.language_id
                JOIN section target_section
                  ON target_section.section_id = target.section_id
                JOIN grimoire target_grimoire
                  ON target_grimoire.grimoire_id = target_section.grimoire_id
                JOIN language_grimoire target_book
                  ON target_book.grimoire_id = target_section.grimoire_id
                 AND target_book.language_id = target_sp.language_id
                WHERE e.embedding_id = ANY(%s::uuid[])
                  AND e.status = 'indexed'
                  AND e.embedding_model_id = %s
                  AND target_section.grimoire_id = %s
                  AND target_sp.language_id = %s
                  AND target_sp.projection_type = %s
                  AND target_sp.direction = %s
                  AND em.vector_size = %s
                  AND em.distance_metric = 'cosine'
                  AND em.qdrant_collection = %s
                  AND target_grimoire.source_metadata->>'demo' = 'true'
                """,
                (
                    sorted(scores), int(source["embedding_model_id"]),
                    int(source["grimoire_id"]), int(source["language_id"]),
                    source["projection_type"], source["direction"],
                    int(source["vector_size"]), source["qdrant_collection"],
                ),
            )
            candidate_rows = list(cur.fetchall())

    return {
        "results": _similar_results(candidate_rows, source=source, scores=scores, k=k),
        "scope": "book",
        "requested_k": k,
        "vector_projection": {
            "field": "semantic_projection.embedding_text",
            "source_embedding_id": source_point_id,
            "projection_type": source["projection_type"],
            "direction": source["direction"],
            "embedding_model_id": int(source["embedding_model_id"]),
            "provider": source["provider"],
            "model_name": source["model_name"],
            "model_revision": source["model_revision"],
            "vector_dimension": int(source["vector_size"]),
            "distance_metric": source["distance_metric"],
            "qdrant_collection": source["qdrant_collection"],
        },
    }


@router.get("/knowledge/{knowledge_id}/neighbors")
def neighbors(knowledge_id: int, request: Request, k: Annotated[int, Query(ge=1, le=25)] = 10):
    _demo_user(request)
    from ..services.discovery import find_neighbors
    return find_neighbors(knowledge_id, k)


@router.get("/crystallize/{knowledge_id}")
def crystallize(knowledge_id: int, request: Request):
    _demo_user(request)
    with transaction() as (_,cur):
        cur.execute("""
            SELECT k.knowledge_crystal_id FROM knowledge k
            JOIN section s ON s.section_id=k.section_id JOIN grimoire g ON g.grimoire_id=s.grimoire_id
            WHERE k.knowledge_id=%s AND k.is_active AND g.source_metadata->>'demo'='true'
        """, (knowledge_id,))
        source=cur.fetchone()
        if not source:
            raise HTTPException(404, 'Knowledge object not found')
        cur.execute("""
            SELECT k.knowledge_id, s.grimoire_id, lk.label, lk.statement, lg.title AS book_title,
                   k.is_default_in_crystal
            FROM knowledge k JOIN section s ON s.section_id=k.section_id
            JOIN grimoire g ON g.grimoire_id=s.grimoire_id
            JOIN language_knowledge lk ON lk.knowledge_id=k.knowledge_id AND lk.language_id=1
            JOIN language_grimoire lg ON lg.grimoire_id=g.grimoire_id AND lg.language_id=1
            WHERE k.knowledge_crystal_id=%s AND k.is_active AND g.source_metadata->>'demo'='true'
            ORDER BY k.is_default_in_crystal DESC, k.knowledge_id
        """, (source['knowledge_crystal_id'],))
        results=list(cur.fetchall())
    return {'results':results, 'knowledge_crystal_id':source['knowledge_crystal_id']}
