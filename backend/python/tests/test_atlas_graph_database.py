"""Exercise stored dependencies through the demo route against disposable PostgreSQL."""
import os
from contextlib import contextmanager

import pytest
from fastapi import Response

from app.database import connect
from app.routers import demo
from app.services.book_ingestion import _upsert_book, _upsert_objects, _upsert_sections

pytestmark = pytest.mark.skipif(
    os.getenv("THEUMST_DATABASE_INTEGRATION") != "1",
    reason="requires disposable PostgreSQL with THEUMST_DATABASE_INTEGRATION=1",
)


def test_atlas_returns_only_active_book_dependencies_and_preserves_order(monkeypatch):
    connection = connect()
    try:
        with connection.cursor() as cur:
            book, language = _upsert_book(cur, {"source_key": "__atlas_graph_test__", "title": "Atlas", "metadata": {"demo": True}})
            sections = _upsert_sections(cur, book, language, [{"source_key": "one", "section_number": "1", "section_name": "One"}])
            objects = _upsert_objects(cur, grimoire_id=book, language_id=language, sections=sections, objects=[
                {"source_key": f"n{i}", "section_source_key": "one", "type": "definition", "label": f"Node {i}", "statement": str(i), "source_metadata": {"order": [i]}}
                for i in range(1, 81)
            ])
            ids = [objects[f"n{i}"]["knowledge_id"] for i in range(1, 81)]
            for i, knowledge_id in enumerate(ids):
                cur.execute("INSERT INTO knowledge_graph_node(grimoire_id,knowledge_id,stable_knowledge_id,graph_role) VALUES(%s,%s,%s,'backbone')", (book, knowledge_id, f"n{i+1}"))
            # Undirected two-hop distance reaches n70 through a common prerequisite.
            pairs = [(1, 2, 'dependency'), (2, 40, 'dependency'), (2, 70, 'dependency'), (39, 40, 'dependency'), (40, 41, 'similarity'), (40, 42, 'generalization'), (40, 43, 'book_order_v1'), (40, 80, 'dependency')]
            for a, b, kind in pairs:
                cur.execute("INSERT INTO knowledge_graph_edge(grimoire_id,source_knowledge_id,target_knowledge_id,relation_type) VALUES(%s,%s,%s,%s)", (book, ids[a-1], ids[b-1], kind))
            cur.execute("UPDATE knowledge SET is_active=false WHERE knowledge_id=%s", (ids[79],))

            @contextmanager
            def transaction():
                yield connection, cur

            monkeypatch.setattr(demo, "transaction", transaction)
            monkeypatch.setattr(demo, "_demo_user", lambda request: {"user_id": 0})
            request = type("Request", (), {"headers": {}})()
            graph = demo.get_grimoire_graph(book, request, Response(), focus=str(ids[39]), ancestor_depth=2, descendant_depth=2, include="support,assessment", limit=150, view="atlas")
            assert graph["authored_dependencies"] is True
            assert {(e['source_knowledge_id'], e['target_knowledge_id']) for e in graph['edges']} == {(ids[a-1], ids[b-1]) for a, b, kind in pairs if kind == 'dependency' and b != 80}
            assert ids[79] not in {n['knowledge_id'] for n in graph['nodes']}
            assert all(e['relation_type'] == 'dependency' for e in graph['edges'])
            assert graph['focus_knowledge_id'] == ids[39]
            assert len(graph['nodes']) <= 150
            assert graph['truncated'] is False

            # Small limits retain the focus and never return dangling edges.
            bounded = demo.get_grimoire_graph(book, request, Response(), focus=str(ids[39]), ancestor_depth=2, descendant_depth=2, include="support,assessment", limit=3, view="atlas")
            chosen = {n['knowledge_id'] for n in bounded['nodes']}
            assert len(chosen) == 3 and ids[39] in chosen
            assert bounded['truncated'] is True
            assert all(e['source_knowledge_id'] in chosen and e['target_knowledge_id'] in chosen for e in bounded['edges'])

            # No authored data still supports book-distance navigation.
            cur.execute("DELETE FROM knowledge_graph_edge WHERE grimoire_id=%s", (book,))
            empty = demo.get_grimoire_graph(book, request, Response(), focus=str(ids[39]), ancestor_depth=2, descendant_depth=2, include="support,assessment", limit=150, view="atlas")
            assert empty['edges'] == [] and empty['authored_dependencies'] is False
            assert len(empty['nodes']) == 49
    finally:
        connection.rollback()
        connection.close()
