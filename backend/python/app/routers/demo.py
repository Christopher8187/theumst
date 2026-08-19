from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from ..database import transaction
from ..dependencies import require_access, require_role, require_user
from ..schemas import (
    DemoAccessRequestPayload,
    DemoNotePayload,
    DemoProgressPayload,
    DemoReviewPayload,
    DemoStudyStatePayload,
)


router = APIRouter(prefix="/api/demo", tags=["web-demo"])
REVIEW_ROLES = {"admin", "superadmin"}
DEMO_VERSION = "0.0.1"
GRAPH_PROJECTION_ALGORITHM = "book_order_v1"
GRAPH_PROJECTION_BACKBONE_TYPES = {"definition", "theorem", "notation"}
GRAPH_PROJECTION_DEFAULT_CHUNK_SIZE = 100
GRAPH_PROJECTION_MIN_CHUNK_SIZE = 50
GRAPH_PROJECTION_MAX_CHUNK_SIZE = 200
GRAPH_PROJECTION_CANVAS_WIDTH = 1000
GRAPH_PROJECTION_ROW_HEIGHT = 128
GRAPH_PROJECTION_SIDE_LANE_SPACING = 200


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
    return {"book": books[0], "contents": sections}


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
        result[section["section_id"]] = list(reversed(chain))[-3:]
    return result


def _canonical_projection_type(value: Any) -> str:
    return str(value or "").strip().lower()


def _projection_revisions(
    rows: list[dict[str, Any]],
    grimoire_id: int | None = None,
) -> tuple[str, str]:
    order_payload = {
        "grimoire_id": grimoire_id,
        "order": [
            [int(row["knowledge_id"]), _canonical_projection_type(row.get("type"))]
            for row in rows
        ],
    }
    encoded = json.dumps(order_payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    book_revision = f"book-order-v1:{hashlib.sha256(encoded).hexdigest()}"
    projection_seed = f"{GRAPH_PROJECTION_ALGORITHM}:{book_revision}".encode("utf-8")
    projection_revision = f"projection-v1:{hashlib.sha256(projection_seed).hexdigest()}"
    return book_revision, projection_revision


def _projection_edge(source_id: int, target_id: int) -> dict[str, Any]:
    return {
        "edge_id": f"{GRAPH_PROJECTION_ALGORITHM}:{source_id}:{target_id}",
        "source_knowledge_id": source_id,
        "target_knowledge_id": target_id,
        "relation_type": GRAPH_PROJECTION_ALGORITHM,
    }


def _compact_fan_lane(fan_ordinal: int) -> int:
    magnitude = (fan_ordinal + 1) // 2
    return -magnitude if fan_ordinal % 2 else magnitude


def _build_graph_projection(
    rows: list[dict[str, Any]],
    grimoire_id: int | None = None,
) -> dict[str, Any]:
    book_revision, projection_revision = _projection_revisions(rows, grimoire_id)
    positions: list[dict[str, int]] = []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    last_backbone_id: int | None = None
    fan_count = 0

    for index, row in enumerate(rows):
        knowledge_id = int(row["knowledge_id"])
        canonical_type = _canonical_projection_type(row.get("type"))
        is_backbone = canonical_type in GRAPH_PROJECTION_BACKBONE_TYPES
        if is_backbone:
            graph_role = "backbone"
            anchor_id = None
            fan_ordinal = 0
            lane = 0
            if last_backbone_id is not None:
                edges.append(_projection_edge(last_backbone_id, knowledge_id))
            last_backbone_id = knowledge_id
            fan_count = 0
        else:
            graph_role = "assessment" if canonical_type in {"exercise", "jas"} else "support"
            anchor_id = last_backbone_id
            if anchor_id is not None:
                fan_count += 1
                fan_ordinal = fan_count
                lane = _compact_fan_lane(fan_ordinal)
                edges.append(_projection_edge(anchor_id, knowledge_id))
            else:
                fan_ordinal = None
                lane = None

        positions.append({
            "knowledge_id": knowledge_id,
            "index": index,
            "type": canonical_type,
            "graph_role": graph_role,
            "anchor_knowledge_id": anchor_id,
            "fan_ordinal": fan_ordinal,
            "lane": lane,
        })
        nodes.append({
            "knowledge_id": knowledge_id,
            "index": index,
            "type": canonical_type,
            "graph_role": graph_role,
            "anchor_knowledge_id": anchor_id,
        })

    return {
        "book_revision": book_revision,
        "projection_revision": projection_revision,
        "positions": positions,
        "nodes": nodes,
        "edges": edges,
    }


def _projection_json(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        value = json.loads(value)
    return list(value or [])


def _projection_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "book_revision": row["book_revision"],
        "projection_revision": row["projection_revision"],
        "positions": _projection_json(row["positions"]),
        "nodes": _projection_json(row["nodes"]),
        "edges": _projection_json(row["edges"]),
    }


def _ensure_stored_graph_projection(
    cur,
    grimoire_id: int,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    book_revision, _ = _projection_revisions(rows, grimoire_id)
    cur.execute(
        """
        SELECT book_revision, projection_revision, positions, nodes, edges
        FROM demo_graph_projection
        WHERE grimoire_id = %s AND book_revision = %s
        """,
        (grimoire_id, book_revision),
    )
    stored = cur.fetchone()
    if stored:
        return _projection_from_row(stored)

    built = _build_graph_projection(rows, grimoire_id)
    cur.execute(
        """
        INSERT INTO demo_graph_projection
            (grimoire_id, book_revision, projection_revision, algorithm,
             positions, nodes, edges)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
        ON CONFLICT (grimoire_id, book_revision) DO NOTHING
        RETURNING book_revision, projection_revision, positions, nodes, edges
        """,
        (
            grimoire_id,
            built["book_revision"],
            built["projection_revision"],
            GRAPH_PROJECTION_ALGORITHM,
            json.dumps(built["positions"], separators=(",", ":")),
            json.dumps(built["nodes"], separators=(",", ":")),
            json.dumps(built["edges"], separators=(",", ":")),
        ),
    )
    stored = cur.fetchone()
    if stored:
        return _projection_from_row(stored)

    # A concurrent transaction may have inserted the same immutable revision.
    cur.execute(
        """
        SELECT book_revision, projection_revision, positions, nodes, edges
        FROM demo_graph_projection
        WHERE grimoire_id = %s AND book_revision = %s
        """,
        (grimoire_id, built["book_revision"]),
    )
    stored = cur.fetchone()
    if not stored:
        raise RuntimeError("Graph projection insert did not produce a stored revision")
    return _projection_from_row(stored)


def _canonical_projection_rows(cur, grimoire_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT 1 AS visible
        FROM grimoire
        WHERE grimoire_id = %s
          AND COALESCE(source_metadata->>'demo', 'false') = 'true'
        """,
        (grimoire_id,),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Demo grimoire not found")
    cur.execute(
        """
        SELECT k.knowledge_id, k.type
        FROM knowledge k
        JOIN section s ON s.section_id = k.section_id
        WHERE s.grimoire_id = %s AND k.is_active
        ORDER BY COALESCE((k.source_metadata->>'demo_order')::int, 2147483647),
                 k.source_metadata->'order' NULLS LAST,
                 k.knowledge_id
        """,
        (grimoire_id,),
    )
    return list(cur.fetchall())


def _bounded_projection_chunk_size(value: int) -> int:
    return max(GRAPH_PROJECTION_MIN_CHUNK_SIZE, min(GRAPH_PROJECTION_MAX_CHUNK_SIZE, int(value)))


def _graph_projection_chunk(
    projection: dict[str, Any],
    chunk_index: int,
    chunk_size: int,
) -> dict[str, Any]:
    if chunk_index < 0:
        raise HTTPException(status_code=404, detail="Projection chunk not found")
    total_nodes = len(projection["nodes"])
    start_index = chunk_index * chunk_size
    if start_index >= total_nodes and not (total_nodes == 0 and chunk_index == 0):
        raise HTTPException(status_code=404, detail="Projection chunk not found")
    end_index = min(start_index + chunk_size, total_nodes)
    index_by_id = {
        int(position["knowledge_id"]): int(position["index"])
        for position in projection["positions"]
    }
    edges = [
        edge for edge in projection["edges"]
        if start_index <= index_by_id[int(edge["target_knowledge_id"])] < end_index
    ]
    return {
        "projection_revision": projection["projection_revision"],
        "chunk_index": chunk_index,
        "start_index": start_index,
        "end_index": end_index,
        "nodes": projection["nodes"][start_index:end_index],
        "edges": edges,
    }


def _current_graph_projection(cur, grimoire_id: int) -> dict[str, Any]:
    rows = _canonical_projection_rows(cur, grimoire_id)
    return _ensure_stored_graph_projection(cur, grimoire_id, rows)


def _latest_stored_graph_projection(cur, grimoire_id: int) -> dict[str, Any]:
    cur.execute(
        """
        SELECT book_revision, projection_revision, positions, nodes, edges
        FROM demo_graph_projection
        WHERE grimoire_id = %s
        ORDER BY created_at DESC, book_revision DESC
        LIMIT 1
        """,
        (grimoire_id,),
    )
    stored = cur.fetchone()
    if not stored:
        raise HTTPException(status_code=404, detail="Graph projection not found")
    return _projection_from_row(stored)


@router.get("/grimoires/{grimoire_id}/graph/projection")
def get_graph_projection_manifest(
    grimoire_id: int,
    request: Request,
    chunk_size: int = GRAPH_PROJECTION_DEFAULT_CHUNK_SIZE,
):
    _demo_user(request)
    bounded_chunk_size = _bounded_projection_chunk_size(chunk_size)
    with transaction() as (_, cur):
        projection = _current_graph_projection(cur, grimoire_id)
    return {
        "projection_revision": projection["projection_revision"],
        "book_revision": projection["book_revision"],
        "total_nodes": len(projection["nodes"]),
        "chunk_size": bounded_chunk_size,
        "canvas_width": GRAPH_PROJECTION_CANVAS_WIDTH,
        "row_height": GRAPH_PROJECTION_ROW_HEIGHT,
        "side_lane_spacing": GRAPH_PROJECTION_SIDE_LANE_SPACING,
        "positions": projection["positions"],
        "initial_chunk": _graph_projection_chunk(projection, 0, bounded_chunk_size),
    }


@router.get("/grimoires/{grimoire_id}/graph/projection/chunks/{chunk_index}")
def get_graph_projection_chunk(
    grimoire_id: int,
    chunk_index: int,
    request: Request,
    chunk_size: int = GRAPH_PROJECTION_DEFAULT_CHUNK_SIZE,
):
    _demo_user(request)
    bounded_chunk_size = _bounded_projection_chunk_size(chunk_size)
    with transaction() as (_, cur):
        projection = _latest_stored_graph_projection(cur, grimoire_id)
    return _graph_projection_chunk(projection, chunk_index, bounded_chunk_size)


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
            SELECT current_knowledge_id, updated_at
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
        node["images"] = list(cur.fetchall())
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
            INSERT INTO demo_study_state (user_id, grimoire_id, current_knowledge_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, grimoire_id) DO UPDATE SET
                current_knowledge_id = EXCLUDED.current_knowledge_id
            """,
            (user["user_id"], grimoire_id, payload.knowledge_id),
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
                   lk.label AS knowledge_label, lg.title AS book_title
            FROM demo_note n
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


@router.get("/crystallize/{knowledge_id}")
def crystallize(knowledge_id: int, request: Request):
    _demo_user(request)
    with transaction() as (_, cur):
        cur.execute(
            """
            SELECT target.knowledge_id, target.type, target_lk.label,
                   target_lk.statement, target_lk.working,
                   target_lk.working_summary,
                   target_section.grimoire_id,
                   target_book.title AS book_title,
                   ds.statement_score, ds.combined_score,
                   (ds.statement_score + ds.combined_score) / 2 AS weighted_score
            FROM demo_similarity ds
            JOIN knowledge target ON target.knowledge_id = ds.to_id
            JOIN language_knowledge target_lk
              ON target_lk.knowledge_id = target.knowledge_id AND target_lk.language_id = 1
            JOIN section target_section ON target_section.section_id = target.section_id
            JOIN language_grimoire target_book
              ON target_book.grimoire_id = target_section.grimoire_id
             AND target_book.language_id = 1
            WHERE ds.from_id = %s
            ORDER BY weighted_score DESC
            """,
            (knowledge_id,),
        )
        rows = list(cur.fetchall())
        for row in rows:
            for key in ("statement_score", "combined_score", "weighted_score"):
                if isinstance(row.get(key), Decimal):
                    row[key] = float(row[key])
    return {"results": rows, "method": "equal_weight_statement_and_combined_embeddings"}
