from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEMO_SOURCE = ROOT / "backend/python/app/routers/demo.py"


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _load_projection_helpers():
    tree = ast.parse(DEMO_SOURCE.read_text(encoding="utf-8"), filename=str(DEMO_SOURCE))
    constants = {
        "GRAPH_PROJECTION_ALGORITHM",
        "GRAPH_PROJECTION_BACKBONE_TYPES",
        "GRAPH_PROJECTION_DEFAULT_CHUNK_SIZE",
        "GRAPH_PROJECTION_MIN_CHUNK_SIZE",
        "GRAPH_PROJECTION_MAX_CHUNK_SIZE",
        "GRAPH_PROJECTION_CANVAS_WIDTH",
        "GRAPH_PROJECTION_ROW_HEIGHT",
        "GRAPH_PROJECTION_SIDE_LANE_SPACING",
    }
    functions = {
        "_canonical_projection_type",
        "_projection_revisions",
        "_projection_edge",
        "_compact_fan_lane",
        "_build_graph_projection",
        "_projection_json",
        "_projection_from_row",
        "_ensure_stored_graph_projection",
        "_bounded_projection_chunk_size",
        "_graph_projection_chunk",
    }
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in constants for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in functions:
            selected.append(node)
    namespace = {
        "Any": Any,
        "HTTPException": HTTPException,
        "hashlib": hashlib,
        "json": json,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(DEMO_SOURCE), "exec"), namespace)
    return SimpleNamespace(**namespace)


demo = _load_projection_helpers()


class ProjectionCursor:
    def __init__(self):
        self.rows = {}
        self.insert_count = 0
        self.result = None

    def execute(self, statement, values):
        sql = " ".join(statement.split())
        if sql.startswith("SELECT book_revision"):
            self.result = self.rows.get((values[0], values[1]))
            return
        if sql.startswith("INSERT INTO demo_graph_projection"):
            key = (values[0], values[1])
            if key in self.rows:
                self.result = None
                return
            self.insert_count += 1
            self.rows[key] = {
                "book_revision": values[1],
                "projection_revision": values[2],
                "positions": json.loads(values[4]),
                "nodes": json.loads(values[5]),
                "edges": json.loads(values[6]),
            }
            self.result = self.rows[key]
            return
        raise AssertionError(f"Unexpected SQL in projection test: {sql}")

    def fetchone(self):
        return self.result


def _rows(*types):
    return [
        {"knowledge_id": index + 1, "type": node_type}
        for index, node_type in enumerate(types)
    ]


def test_projection_exact_spine_previous_main_fan_and_stable_edges():
    rows = _rows(
        "context",
        " Definition ",
        "exercise",
        "context",
        "THEOREM",
        "notation ",
        "definition-like",
    )
    projection = demo._build_graph_projection(rows)
    assert projection == demo._build_graph_projection(rows)

    nodes = projection["nodes"]
    assert [node["knowledge_id"] for node in nodes if node["graph_role"] == "backbone"] == [2, 5, 6]
    assert nodes[0]["anchor_knowledge_id"] is None
    assert projection["positions"][0]["fan_ordinal"] is None
    assert projection["positions"][0]["lane"] is None
    assert all(edge["target_knowledge_id"] != 1 for edge in projection["edges"])
    assert nodes[2]["anchor_knowledge_id"] == 2
    assert nodes[3]["anchor_knowledge_id"] == 2
    assert nodes[6]["anchor_knowledge_id"] == 6

    pairs = [
        (edge["source_knowledge_id"], edge["target_knowledge_id"])
        for edge in projection["edges"]
    ]
    assert pairs == [(2, 3), (2, 4), (2, 5), (5, 6), (6, 7)]
    assert [edge["edge_id"] for edge in projection["edges"]] == [
        "book_order_v1:2:3",
        "book_order_v1:2:4",
        "book_order_v1:2:5",
        "book_order_v1:5:6",
        "book_order_v1:6:7",
    ]
    assert {edge["relation_type"] for edge in projection["edges"]} == {"book_order_v1"}


def test_far_late_fans_reset_to_compact_lanes_after_each_spine_item():
    rows = _rows("definition", *(["context"] * 20), "theorem", *(["exercise"] * 20))
    positions = demo._build_graph_projection(rows)["positions"]
    assert [position["lane"] for position in positions[1:5]] == [-1, 1, -2, 2]
    assert positions[20]["fan_ordinal"] == 20
    assert positions[20]["lane"] == 10
    assert positions[21]["graph_role"] == "backbone"
    assert positions[21]["lane"] == 0
    assert positions[22]["fan_ordinal"] == 1
    assert positions[22]["lane"] == -1
    assert positions[22]["anchor_knowledge_id"] == positions[21]["knowledge_id"]
    assert [position["lane"] for position in positions[22:26]] == [-1, 1, -2, 2]


def test_projection_persists_reuses_and_invalidates_only_on_order_fingerprint_change():
    cursor = ProjectionCursor()
    original_rows = _rows("definition", "context", "theorem")
    first = demo._ensure_stored_graph_projection(cursor, 7, original_rows)
    second = demo._ensure_stored_graph_projection(cursor, 7, [dict(row) for row in original_rows])
    assert second == first
    assert cursor.insert_count == 1
    assert len(cursor.rows) == 1

    changed_order = [original_rows[1], original_rows[0], original_rows[2]]
    changed = demo._ensure_stored_graph_projection(cursor, 7, changed_order)
    assert changed["book_revision"] != first["book_revision"]
    assert changed["projection_revision"] != first["projection_revision"]
    assert cursor.insert_count == 2
    assert len(cursor.rows) == 2
    assert first == demo._ensure_stored_graph_projection(cursor, 7, original_rows)
    assert cursor.insert_count == 2


def test_projection_delivers_three_chunks_and_clamps_limits():
    projection = demo._build_graph_projection(_rows(*(["definition"] * 205)))
    chunks = [demo._graph_projection_chunk(projection, index, 100) for index in range(3)]
    assert [(chunk["start_index"], chunk["end_index"]) for chunk in chunks] == [
        (0, 100),
        (100, 200),
        (200, 205),
    ]
    assert [len(chunk["nodes"]) for chunk in chunks] == [100, 100, 5]
    assert [len(chunk["edges"]) for chunk in chunks] == [99, 100, 5]
    assert demo._bounded_projection_chunk_size(1) == 50
    assert demo._bounded_projection_chunk_size(100) == 100
    assert demo._bounded_projection_chunk_size(999) == 200
    try:
        demo._graph_projection_chunk(projection, 3, 100)
    except HTTPException as missing:
        assert missing.status_code == 404
    else:
        raise AssertionError("an out-of-range projection chunk must be rejected")


def test_manifest_and_chunk_routes_keep_demo_authority_and_contract():
    source = DEMO_SOURCE.read_text(encoding="utf-8")
    manifest = source.split("def get_graph_projection_manifest", 1)[1].split(
        "@router.get(\"/grimoires/{grimoire_id}/graph/projection/chunks", 1
    )[0]
    chunk = source.split("def get_graph_projection_chunk", 1)[1].split(
        "@router.get(\"/grimoires/{grimoire_id}/knowledge\")", 1
    )[0]
    assert '@router.get("/grimoires/{grimoire_id}/graph/projection")' in source
    assert '@router.get("/grimoires/{grimoire_id}/graph/projection/chunks/{chunk_index}")' in source
    assert "_demo_user(request)" in manifest
    assert "_demo_user(request)" in chunk
    assert "_current_graph_projection" in manifest
    assert "_latest_stored_graph_projection" in chunk
    assert "_current_graph_projection" not in chunk
    for field in (
        "projection_revision", "book_revision", "total_nodes", "chunk_size",
        "canvas_width", "row_height", "side_lane_spacing", "positions", "initial_chunk"
    ):
        assert f'"{field}"' in manifest
    for field in ("projection_revision", "chunk_index", "start_index", "end_index", "nodes", "edges"):
        assert f'"{field}"' in source.split("def _graph_projection_chunk", 1)[1]


def test_demo_projection_migration_is_immutable_and_demo_owned():
    migration = (ROOT / "backend/sql/006_demo_graph_projection.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS demo_graph_projection" in migration
    assert "PRIMARY KEY (grimoire_id, book_revision)" in migration
    assert "CHECK (algorithm = 'book_order_v1')" in migration
    assert "UPDATE demo_graph_projection" not in migration


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"demo-graph-projection: {len(tests)} focused tests passed")
