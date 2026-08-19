from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException
from psycopg2 import extras as psycopg2_extras

# The repository's test-only psycopg2 shim exposes RealDictCursor but not this
# production helper. Graph tests never execute it; provide an import sentinel.
if not hasattr(psycopg2_extras, "execute_values"):
    psycopg2_extras.execute_values = None

from app.services import book_ingestion, graph_sidecar
from app.services.book_ingestion import _validate_manifest
from app.services.graph_sidecar import (
    BOOK_ORDER_PROJECTION_VERSION,
    BOOK_ORDER_RELATION_TYPE,
    BookOrderProjectionError,
    GraphSidecarValidationError,
    build_book_order_v1_projection,
    build_contents_tree,
    fetch_focused_graph,
    slice_book_order_v1_projection,
    validate_graph_sidecar,
)


def objects() -> list[dict]:
    return [
        {"source_key": "definition:group", "type": "definition"},
        {"source_key": "exercise:one", "type": "exercise"},
        {"source_key": "jas:hint", "type": "jas"},
    ]


def valid_sidecar(*, relations: list[dict] | None = None) -> dict:
    return {
        "contract_version": 1,
        "graph_revision": "book-graph-2026-08-17",
        "nodes": [
            {
                "knowledge_id": "book:definition:group",
                "object_source_key": "definition:group",
                "graph_role": "backbone",
            },
            {
                "knowledge_id": "book:exercise:one",
                "object_source_key": "exercise:one",
                "graph_role": "assessment",
            },
            {
                "knowledge_id": "book:jas:hint",
                "object_source_key": "jas:hint",
                "graph_role": "support",
            },
        ],
        "relations": relations or [],
    }


def test_relationless_sidecar_is_explicit_and_does_not_invent_edges():
    graph = validate_graph_sidecar(valid_sidecar(), objects())

    assert graph.relations == ()
    assert graph.receipt.valid is True
    assert graph.receipt.capability == "relations_declared_empty"
    assert [node.knowledge_id for node in graph.nodes] == [
        "book:definition:group",
        "book:exercise:one",
        "book:jas:hint",
    ]


def test_validation_receipt_and_diagnostics_are_deterministic():
    sidecar = valid_sidecar(relations=[
        {
            "source_knowledge_id": "book:definition:group",
            "target_knowledge_id": "book:exercise:one",
            "relation_type": "assesses",
        },
        {
            "source_knowledge_id": "book:definition:group",
            "target_knowledge_id": "book:exercise:one",
            "relation_type": "assesses",
        },
    ])

    first = validate_graph_sidecar(sidecar, objects())
    second = validate_graph_sidecar(sidecar, objects())

    assert first.receipt == second.receipt
    assert len(first.relations) == 1
    assert first.receipt.duplicate_relations == (
        ("book:definition:group", "book:exercise:one", "assesses"),
    )


def test_orphans_are_rejected_and_sorted_in_receipt():
    sidecar = valid_sidecar(relations=[
        {
            "source_knowledge_id": "missing:z",
            "target_knowledge_id": "book:definition:group",
            "relation_type": "depends_on",
        },
        {
            "source_knowledge_id": "missing:a",
            "target_knowledge_id": "book:definition:group",
            "relation_type": "depends_on",
        },
    ])

    with pytest.raises(GraphSidecarValidationError) as caught:
        validate_graph_sidecar(sidecar, objects())

    assert caught.value.receipt.orphan_references == ("missing:a", "missing:z")
    assert caught.value.receipt.capability == "invalid"


def test_directed_cycles_are_rejected_as_sorted_components():
    sidecar = valid_sidecar(relations=[
        {
            "source_knowledge_id": "book:exercise:one",
            "target_knowledge_id": "book:definition:group",
            "relation_type": "depends_on",
        },
        {
            "source_knowledge_id": "book:definition:group",
            "target_knowledge_id": "book:exercise:one",
            "relation_type": "depends_on",
        },
    ])

    with pytest.raises(GraphSidecarValidationError) as caught:
        validate_graph_sidecar(sidecar, objects())

    assert caught.value.receipt.cycle_components == (
        ("book:definition:group", "book:exercise:one"),
    )


@pytest.mark.parametrize("object_key", ["exercise:one", "jas:hint"])
def test_exercise_and_jas_cannot_be_backbone(object_key: str):
    sidecar = valid_sidecar()
    for node in sidecar["nodes"]:
        if node["object_source_key"] == object_key:
            node["graph_role"] = "backbone"

    with pytest.raises(GraphSidecarValidationError, match="support or assessment"):
        validate_graph_sidecar(sidecar, objects())


def test_graph_roles_are_validated_without_type_based_inference():
    sidecar = valid_sidecar()
    sidecar["nodes"][0]["graph_role"] = "main"

    with pytest.raises(GraphSidecarValidationError) as caught:
        validate_graph_sidecar(sidecar, objects())

    assert any("graph_role must be one of" in error for error in caught.value.receipt.errors)


def test_graph_sidecar_is_optional_for_legacy_manifest_but_versioned_when_present():
    legacy = {
        "schema_version": 1,
        "book": {"source_key": "book", "title": "Book"},
        "sections": [],
        "objects": [],
        "embeddings": [],
        "images": [],
    }
    _validate_manifest(legacy)

    legacy["knowledge_graph"] = {
        "contract_version": 1,
        "graph_revision": "revision",
        "nodes": [],
        "relations": [],
    }
    with pytest.raises(HTTPException, match="schema_version 2"):
        _validate_manifest(legacy)

    legacy["schema_version"] = 2
    _validate_manifest(legacy)


def test_legacy_ingestion_without_sidecar_leaves_graph_state_unchanged():
    source = inspect.getsource(book_ingestion.ingest_book_archive)
    assert "if graph is not None:" in source
    assert "invalidate_graph" not in source
    assert 'graph_capability = "unchanged"' in source


def test_contents_uses_actual_parent_metadata_and_reports_bad_metadata():
    contents = build_contents_tree([
        {
            "section_id": 3,
            "parent_section": 1,
            "section_source_key": "section:child",
            "section_number": "1.1",
            "section_name": "Child",
        },
        {
            "section_id": 1,
            "parent_section": None,
            "section_source_key": "section:root",
            "section_number": "1",
            "section_name": "Root",
        },
        {
            "section_id": 4,
            "parent_section": 999,
            "section_source_key": "section:orphan",
            "section_number": "2",
            "section_name": "Orphan",
        },
    ])

    assert contents["sections"][0]["section_source_key"] == "section:root"
    assert contents["sections"][0]["children"][0]["section_source_key"] == "section:child"
    assert contents["orphan_section_ids"] == [4]
    assert contents["cycle_section_ids"] == []


def test_contents_cycle_is_reported_without_creating_recursive_json():
    contents = build_contents_tree([
        {"section_id": 1, "parent_section": 2, "section_number": "1"},
        {"section_id": 2, "parent_section": 1, "section_number": "2"},
    ])

    assert contents["cycle_section_ids"] == [1, 2]
    assert len(contents["sections"]) == 2
    assert all(section["children"] == [] for section in contents["sections"])


def projected_item(
    knowledge_id: int,
    position: list[int],
    working_type: str,
    *,
    graph_role: str | None = None,
) -> dict:
    item = {
        "knowledge_id": knowledge_id,
        "canonical_book_position": position,
        "type": working_type,
        "label": f"Item {knowledge_id}",
    }
    if graph_role is not None:
        item["graph_role"] = graph_role
    return item


def edge_pairs(projection: dict) -> list[tuple[int, int]]:
    return [
        (edge["source_knowledge_id"], edge["target_knowledge_id"])
        for edge in projection["edges"]
    ]


def test_book_order_v1_exact_spine_and_fan_example():
    projection = build_book_order_v1_projection([
        projected_item(1, [1], "definition"),
        projected_item(2, [2], "context"),
        projected_item(3, [3], "context"),
        projected_item(4, [4], "theorem"),
        projected_item(5, [5], "context"),
    ])

    assert edge_pairs(projection) == [(1, 2), (1, 3), (1, 4), (4, 5)]
    assert [node["graph_role"] for node in projection["nodes"]] == [
        "backbone", "support", "support", "backbone", "support",
    ]
    assert projection["projection_metadata"] == {
        "version": "book_order_v1",
        "relation_type": "book_order",
        "source": "knowledge.source_metadata.order",
        "authored_dependencies": False,
        "leading_non_main_anchor_knowledge_id": None,
    }
    assert all(edge["authored_relation"] is False for edge in projection["edges"])


def test_book_order_v1_multiple_consecutive_main_items_form_spine():
    projection = build_book_order_v1_projection([
        projected_item(1, [1], "definition"),
        projected_item(2, [2], "theorem"),
        projected_item(3, [3], "lemma"),
    ])

    assert edge_pairs(projection) == [(1, 2), (2, 3)]


def test_book_order_v1_leading_non_main_prefix_uses_provisional_anchor():
    projection = build_book_order_v1_projection([
        projected_item(1, [1], "context"),
        projected_item(2, [2], "context"),
        projected_item(3, [3], "definition"),
        projected_item(4, [4], "context"),
    ])

    assert edge_pairs(projection) == [(1, 2), (1, 3), (3, 4)]
    assert projection["nodes"][0]["graph_role"] == "support"
    assert projection["nodes"][0]["is_provisional_anchor"] is True
    assert projection["projection_metadata"]["leading_non_main_anchor_knowledge_id"] == 1


def test_book_order_v1_trailing_non_main_items_remain_a_fan():
    projection = build_book_order_v1_projection([
        projected_item(1, [1], "definition"),
        projected_item(2, [2], "theorem"),
        projected_item(3, [3], "context"),
        projected_item(4, [4], "context"),
        projected_item(5, [5], "context"),
    ])

    assert edge_pairs(projection) == [(1, 2), (2, 3), (2, 4), (2, 5)]


def test_book_order_v1_jas_and_exercise_never_take_the_anchor():
    projection = build_book_order_v1_projection([
        projected_item(1, [1], "definition"),
        projected_item(2, [2], "jas", graph_role="backbone"),
        projected_item(3, [3], "exercise", graph_role="backbone"),
        projected_item(4, [4], "theorem"),
        projected_item(5, [5], "context"),
    ])

    assert edge_pairs(projection) == [(1, 2), (1, 3), (1, 4), (4, 5)]
    roles = {node["knowledge_id"]: node["graph_role"] for node in projection["nodes"]}
    assert roles[2] == "support"
    assert roles[3] == "assessment"


def test_book_order_v1_stable_id_tie_break_and_strict_forward_invariant():
    projection = build_book_order_v1_projection([
        projected_item(9, [2], "context"),
        projected_item(7, [1], "definition"),
        projected_item(3, [2], "theorem"),
        projected_item(11, [3], "exercise"),
    ])
    node_order = [node["knowledge_id"] for node in projection["nodes"]]
    order_index = {knowledge_id: rank for rank, knowledge_id in enumerate(node_order)}

    assert node_order == [7, 3, 9, 11]
    assert edge_pairs(projection) == [(7, 3), (3, 9), (3, 11)]
    assert all(order_index[source] < order_index[target] for source, target in edge_pairs(projection))
    assert len(set(edge_pairs(projection))) == len(edge_pairs(projection))


def test_book_order_v1_single_item_has_no_edge_and_invalid_order_fails():
    projection = build_book_order_v1_projection([
        projected_item(1, [1], "definition"),
    ])
    assert edge_pairs(projection) == []

    for bad_position in (None, [], [1.5], [-1], [True], ["1"]):
        with pytest.raises(BookOrderProjectionError, match="Canonical book position"):
            build_book_order_v1_projection([
                projected_item(1, bad_position, "definition"),
            ])


def test_book_order_v1_focused_slice_is_bounded_and_counts_collapsed_fan():
    projection = build_book_order_v1_projection([
        projected_item(1, [1], "definition"),
        *[
            projected_item(knowledge_id, [knowledge_id], "context")
            for knowledge_id in range(2, 202)
        ],
        projected_item(202, [202], "theorem"),
    ])
    sliced = slice_book_order_v1_projection(
        projection,
        focus=1,
        ancestor_depth=0,
        descendant_depth=1,
        limit=150,
    )

    assert len(sliced["nodes"]) == 150
    assert len(sliced["edges"]) == 149
    focus_node = next(node for node in sliced["nodes"] if node["knowledge_id"] == 1)
    assert focus_node["collapsed_descendant_count"] == 52
    assert sliced["projection_metadata"]["version"] == BOOK_ORDER_PROJECTION_VERSION


def test_focused_graph_query_is_book_scoped_bounded_and_explicitly_projected():
    source = " ".join(inspect.getsource(fetch_focused_graph).lower().split())
    assert graph_sidecar.FOCUSED_GRAPH_MAX_NODES == 150
    assert graph_sidecar.FOCUSED_GRAPH_MAX_DEPTH == 2
    assert source.count("limit %s") == 1
    assert "s.grimoire_id = %s" in source
    assert "source_metadata->'order'" in source
    assert "jsonb_array_elements" in source
    assert "position_rank > 1" in source
    assert "knowledge_graph_edge" not in source
    assert " from similarity " not in source
    assert " join similarity " not in source
    assert BOOK_ORDER_RELATION_TYPE == "book_order"
    assert BOOK_ORDER_PROJECTION_VERSION == "book_order_v1"


class ScriptedCursor:
    def __init__(self, results: list[list[dict]]):
        self.results = list(results)
        self.current: list[dict] = []
        self.queries: list[tuple[str, object]] = []

    def execute(self, query: str, parameters=None):
        self.queries.append((query, parameters))
        self.current = self.results.pop(0)

    def fetchone(self):
        return self.current[0] if self.current else None

    def fetchall(self):
        return self.current


def test_focused_graph_returns_numeric_canonical_ids_and_additive_stable_ids():
    cursor = ScriptedCursor([
        [{
            "total_count": 1,
            "invalid_count": 0,
            "focus_exists": True,
            "projection_digest": "abc",
            "leading_non_main_anchor_knowledge_id": None,
            "nodes": [{
                "knowledge_id": 10,
                "stable_knowledge_id": "book:def",
                "graph_role": "backbone",
                "label": "Definition",
                "type": "definition",
                "collapsed_ancestor_count": 0,
                "collapsed_descendant_count": 0,
            }],
            "edges": [],
        }],
    ])

    graph = fetch_focused_graph(
        cursor,
        grimoire_id=7,
        focus=10,
        ancestor_depth=0,
        descendant_depth=0,
    )

    assert graph["focus_knowledge_id"] == 10
    assert graph["nodes"][0]["knowledge_id"] == 10
    assert graph["nodes"][0]["stable_knowledge_id"] == "book:def"
    assert graph["edges"] == []
    assert graph["graph_revision"] == "book_order_v1:abc"
    assert graph["graph_capability"] == "book_order_projection"
    assert graph["projection_metadata"]["authored_dependencies"] is False
    assert len(cursor.queries) == 1
    query, parameters = cursor.queries[0]
    assert parameters[2] == 7
    assert parameters[10] == 150
    assert "LIMIT %s" in query


def test_focused_graph_fails_honestly_for_ambiguous_order_before_missing_focus():
    cursor = ScriptedCursor([
        [{
            "total_count": 1,
            "invalid_count": 1,
            "focus_exists": False,
            "projection_digest": "",
            "leading_non_main_anchor_knowledge_id": None,
            "nodes": [],
            "edges": [],
        }],
    ])

    with pytest.raises(BookOrderProjectionError, match="unambiguous canonical order"):
        fetch_focused_graph(cursor, grimoire_id=7, focus=10)


def test_focused_graph_missing_focus_is_indistinguishable_after_valid_projection():
    cursor = ScriptedCursor([[{
        "total_count": 2,
        "invalid_count": 0,
        "focus_exists": False,
        "projection_digest": "abc",
        "leading_non_main_anchor_knowledge_id": None,
        "nodes": [],
        "edges": [],
    }]])

    with pytest.raises(LookupError, match="not available"):
        fetch_focused_graph(cursor, grimoire_id=7, focus=99)


@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"limit": 151}, "limit must be between"),
        ({"ancestor_depth": 3}, "graph depths must be between"),
    ],
)
def test_focused_graph_rejects_unbounded_requests(arguments: dict, message: str):
    with pytest.raises(ValueError, match=message):
        fetch_focused_graph(ScriptedCursor([]), grimoire_id=7, focus=10, **arguments)


def test_schema_enforces_book_scoped_graph_identity_and_keeps_similarity_separate():
    root = Path(__file__).resolve().parents[3]
    schema = (root / "backend" / "sql" / "schema.sql").read_text(encoding="utf-8")
    migration = (root / "backend" / "sql" / "006_knowledge_graph.sql").read_text(encoding="utf-8")

    for sql in (schema, migration):
        assert "knowledge_graph_node" in sql
        assert "stable_knowledge_id" in sql
        assert "knowledge_graph_receipt" in sql
        assert "FOREIGN KEY (grimoire_id, source_knowledge_id)" in sql
        assert "FOREIGN KEY (grimoire_id, target_knowledge_id)" in sql
        assert "graph_capability" in sql
    graph_block = schema[schema.index("-- Optional, versioned knowledge-graph"):schema.index("CREATE TABLE IF NOT EXISTS similarity")]
    assert "FROM similarity" not in graph_block
    assert "REFERENCES similarity" not in graph_block


def _normalized_sql_statements(sql: str) -> list[str]:
    uncommented = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
    return [" ".join(statement.split()) for statement in uncommented.split(";") if statement.strip()]


def test_migration_exactly_matches_fresh_graph_contract_and_has_no_draft_schema():
    root = Path(__file__).resolve().parents[3]
    schema = (root / "backend" / "sql" / "schema.sql").read_text(encoding="utf-8")
    migration = (root / "backend" / "sql" / "006_knowledge_graph.sql").read_text(encoding="utf-8")
    graph_block = schema[
        schema.index("-- Optional, versioned knowledge-graph"):
        schema.index("CREATE TABLE IF NOT EXISTS similarity")
    ]

    assert _normalized_sql_statements(migration) == _normalized_sql_statements(graph_block)
    assert "ALTER TABLE knowledge" not in migration
    assert "knowledge_graph_rejection" not in migration
    assert "anchor_knowledge_id" not in migration
    assert "is_canonical" not in migration
    assert "provenance" not in migration
    assert "PRIMARY KEY (grimoire_id, source_knowledge_id, target_knowledge_id, relation_type)" in migration
    assert "CHECK (relation_type ~ '^[a-z][a-z0-9_.:-]*$')" in migration
    assert migration.count("CREATE TABLE IF NOT EXISTS knowledge_graph_") == 3
    assert migration.count("CREATE INDEX IF NOT EXISTS knowledge_graph_") == 3
