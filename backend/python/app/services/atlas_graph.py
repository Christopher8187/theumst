"""Bounded Atlas input from explicit, book-scoped dependency edges."""
from __future__ import annotations

from typing import Any

MAX_NODES = 150
MAX_BOOK_DISTANCE = 24
MAX_DEPENDENCY_DISTANCE = 8
EDGES_PER_NODE = 4

# Match the complete reader list, including its fallback for older imports.
# Both endpoints must still be active members of this book. Other relation
# types, legacy cross-book relations and generated order never enter this view.
_BOOK = """
WITH visible AS (
    SELECT k.knowledge_id, k.type,
           row_number() OVER (
               ORDER BY COALESCE((k.source_metadata->>'demo_order')::int, 2147483647),
                        k.source_metadata->'order' NULLS LAST, k.knowledge_id
           )::int AS book_order_rank
    FROM knowledge k JOIN section s ON s.section_id = k.section_id
    WHERE s.grimoire_id = %(book)s AND k.is_active
), dependencies AS (
    SELECT edge.source_knowledge_id, edge.target_knowledge_id
    FROM knowledge_graph_edge edge
    JOIN visible source ON source.knowledge_id = edge.source_knowledge_id
    JOIN visible target ON target.knowledge_id = edge.target_knowledge_id
    WHERE edge.grimoire_id = %(book)s AND edge.relation_type = 'dependency'
      AND edge.source_knowledge_id <> edge.target_knowledge_id
)
"""


def fetch_atlas_graph(cur, *, grimoire_id: int, focus: str | int,
                      limit: int = MAX_NODES, language_id: int = 1) -> dict[str, Any]:
    """Fetch a superset for both distance sliders, with bounded driver transfers.

    Start with up to 49 adjacent reader positions and walk dependencies without
    direction for at most eight steps. Each read is capped; dense books report
    truncation instead of transferring all relationships. The browser applies
    its independent distance controls and the smaller 24-object/72-arrow limits.
    """
    if not 1 <= limit <= MAX_NODES:
        raise ValueError(f"limit must be between 1 and {MAX_NODES}")
    if not str(focus).isdigit():
        raise LookupError("The focus knowledge item is not available in this book")
    focus_id = int(focus)
    params = {"book": grimoire_id, "focus": focus_id, "limit": limit + 1,
              "book_distance": MAX_BOOK_DISTANCE}
    cur.execute(_BOOK + """
        SELECT node.knowledge_id
        FROM visible node JOIN visible focus ON focus.knowledge_id = %(focus)s
        WHERE abs(node.book_order_rank - focus.book_order_rank) <= %(book_distance)s
        ORDER BY abs(node.book_order_rank - focus.book_order_rank), node.book_order_rank
        LIMIT %(limit)s
    """, params)
    rows = cur.fetchall()
    if not rows:
        raise LookupError("The focus knowledge item is not available in this book")
    selected = {int(row["knowledge_id"]) for row in rows[:limit]}
    truncated = len(rows) > limit
    visited, frontier = {focus_id}, [focus_id]
    for _ in range(MAX_DEPENDENCY_DISTANCE):
        if not frontier:
            break
        # Already-selected book neighbours must remain traversable; they do not
        # consume additional capacity. Never transfer more than 151 candidates.
        capacity = limit - len(selected)
        params.update(frontier=frontier, visited=sorted(visited),
                      candidate_limit=capacity + len(selected - visited) + 1)
        cur.execute(_BOOK + """
            , candidates AS (
                SELECT source_knowledge_id AS knowledge_id FROM dependencies
                WHERE target_knowledge_id = ANY(%(frontier)s::int[])
                UNION
                SELECT target_knowledge_id FROM dependencies
                WHERE source_knowledge_id = ANY(%(frontier)s::int[])
            )
            SELECT candidate.knowledge_id
            FROM candidates candidate JOIN visible node USING (knowledge_id)
            JOIN visible focus ON focus.knowledge_id = %(focus)s
            WHERE NOT (candidate.knowledge_id = ANY(%(visited)s::int[]))
            ORDER BY abs(node.book_order_rank - focus.book_order_rank), node.book_order_rank
            LIMIT %(candidate_limit)s
        """, params)
        frontier = []
        for row in cur.fetchall():
            candidate = int(row["knowledge_id"])
            if candidate not in selected and len(selected) >= limit:
                truncated = True
                continue
            selected.add(candidate)
            visited.add(candidate)
            frontier.append(candidate)

    params.update(selected=sorted(selected), language=language_id, limit=limit)
    cur.execute(_BOOK + """
        SELECT node.knowledge_id, node.type, node.book_order_rank,
               COALESCE(lk.label, lk.statement, node.knowledge_id::text) AS label,
               COALESCE(explicit.graph_role, 'fragment') AS graph_role,
               explicit.stable_knowledge_id
        FROM visible node
        LEFT JOIN language_knowledge lk ON lk.knowledge_id = node.knowledge_id
          AND lk.language_id = %(language)s
        LEFT JOIN knowledge_graph_node explicit ON explicit.knowledge_id = node.knowledge_id
          AND explicit.grimoire_id = %(book)s
        WHERE node.knowledge_id = ANY(%(selected)s::int[])
        ORDER BY node.book_order_rank LIMIT %(limit)s
    """, params)
    nodes = [dict(row) for row in cur.fetchall()]
    edge_limit = limit * EDGES_PER_NODE
    params["edge_limit"] = edge_limit + 1
    cur.execute(_BOOK + """
        SELECT source_knowledge_id, target_knowledge_id, 'dependency' AS relation_type
        FROM dependencies
        WHERE source_knowledge_id = ANY(%(selected)s::int[])
          AND target_knowledge_id = ANY(%(selected)s::int[])
        ORDER BY source_knowledge_id, target_knowledge_id LIMIT %(edge_limit)s
    """, params)
    edges = [dict(row) for row in cur.fetchall()]
    return {
        "nodes": nodes,
        "edges": edges[:edge_limit],
        "focus_knowledge_id": focus_id,
        "graph_revision": "atlas_dependencies_v1",
        "graph_capability": "authored_dependencies" if edges else "book_positions",
        "authored_dependencies": bool(edges),
        "edges_truncated": len(edges) > edge_limit,
        "truncated": truncated or len(edges) > edge_limit,
    }
