"""The whole-book reads (0.0.15, and the game's in 0.0.16): their answers, the Web Demo
route's answers and headers, migrations 016 and 017, and the operator command, with scripted
stand-ins for PostgreSQL.

These establish the shape and order of the answers built from given rows, the order of the
route's checks, its caching headers, that one gzip layer reaches the client, and the
command's lines and exit codes. test_game_books.py checks the game's routes the same way, and
test_book_read_postgres.py checks both against PostgreSQL, through ingestion and the application.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import dependencies, reviewed_migrations
from app.config import get_settings
from app.main import create_app
from app.routers import demo
from app.services import book_read
from scripts import build_book_reads


ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = ROOT / "backend/sql/016_book_read.sql"
GAME_MIGRATION_PATH = ROOT / "backend/sql/017_book_game_read.sql"
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
BOOK_READ_MIGRATION = next(
    migration for migration in reviewed_migrations.REVIEWED_MIGRATIONS if migration.key == "book_read_v1"
)
BOOK_GAME_READ_MIGRATION = next(
    migration for migration in reviewed_migrations.REVIEWED_MIGRATIONS if migration.key == "book_game_read_v1"
)
ROUTE = "/api/demo/grimoires/{grimoire_id}/book-read"
TWO_WEEKS = "private, max-age=1209600"


# --- the answer -----------------------------------------------------------------------

def section(section_id, parent, number, name=None, own=None, whole=None):
    return {"section_id": section_id, "parent_section": parent, "section_number": number,
            "section_name": name, "minutes_own": own, "minutes_whole": whole}


def test_sections_follow_the_contents_tree_depth_first():
    rows = [
        section(5, 1, "002"), section(1, None, "001"), section(3, 1, "001"), section(4, 3, "001"),
        section(2, None, "002"), section(9, 2, "001"),
        section(7, 999, "001"), section(8, 7, "001"),  # an orphan, whose parent is not in the book, and its child
        section(11, 12, "009"), section(12, 11, "008"),  # a parent cycle: both become roots
    ]
    order = [(row["section_id"], depth) for row, depth in book_read.contents_order(rows)]
    assert order == [(1, 0), (3, 1), (4, 2), (5, 1), (2, 0), (9, 1), (12, 0), (11, 0), (7, 0), (8, 1)]


def test_sections_sort_their_numbers_as_text_then_by_id():
    rows = [section(1, None, "10"), section(2, None, "9"), section(3, None, "10")]
    assert [row["section_id"] for row, _ in book_read.contents_order(rows)] == [1, 3, 2]


def test_the_version_is_the_hash_of_the_answer_without_it():
    answer = {"format": 1, "grimoire_id": 18, "name": "Ω", "list": [3, 1], "nested": {"b": 1, "a": 0.5}}
    built = book_read.encode(answer)
    canonical = json.dumps(answer, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert built.version == hashlib.sha256(canonical).hexdigest()
    assert built.body == json.dumps({**answer, "version": built.version}, ensure_ascii=False,
                                    separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert b'"name":"\xce\xa9"' in built.body  # UTF-8, not escaped
    assert gzip.decompress(built.body_gzip) == built.body
    assert built.body_gzip[4:8] == b"\0\0\0\0"  # mtime 0, so the same facts give the same bytes
    assert book_read.encode(dict(answer)).body_gzip == built.body_gzip
    with pytest.raises(ValueError):
        book_read.encode({"grimoire_id": 1, "difficulty": float("inf")})
    with pytest.raises(ValueError):
        book_read.encode(built.answer)


class Rows:
    """Answers the build's queries from fixed rows, and keeps every statement."""

    def __init__(self, *, book=True, sections=(), objects=(), edges=(), stored=None, fail=None,
                 failure="the build broke " + "x" * 600, texts=None, figures=(), pages=(), stored_game=None):
        self.book, self.sections, self.objects, self.edges = book, sections, objects, edges
        self.stored, self.fail, self.failure = stored, fail, failure
        self.texts, self.figures, self.pages, self.stored_game = texts, figures, pages, stored_game
        self.statements: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        self.statements.append((text, params))
        if self.fail and self.fail in text:
            raise RuntimeError(self.failure)

    def _last(self):
        return self.statements[-1][0]

    def fetchone(self):
        sql = self._last()
        if sql.startswith("SELECT grimoire_id, graph_capability FROM grimoire"):
            return {"grimoire_id": 18, "graph_capability": "semantic_relations"} if self.book else None
        if sql.startswith("SELECT format, version FROM book_read"):
            return self.stored
        if sql.startswith("SELECT format, version FROM book_game_read"):
            return self.stored_game
        raise AssertionError(f"unexpected fetchone: {sql}")

    def fetchall(self):
        sql = self._last()
        if "lk.statement" in sql:
            if self.texts is not None:
                return list(self.texts)
            return [{"id": row["id"], "statement": f"Statement {row['id']}", "working": "",
                     "working_summary": None} for row in self.objects]
        if "link_type = 'figure'" in sql:
            return list(self.figures)
        if "link_type = 'page'" in sql:
            return list(self.pages)
        if "FROM section s" in sql:
            return list(self.sections)
        if "FROM knowledge k" in sql:
            return list(self.objects)
        if "FROM knowledge_graph_edge" in sql:
            return list(self.edges)
        raise AssertionError(f"unexpected fetchall: {sql}")

    def ran(self, fragment):
        return [params for sql, params in self.statements if fragment in sql]


def obj(knowledge_id, crystal_id, section_id=1801, role="backbone", **extra):
    return {"id": knowledge_id, "section_id": section_id, "type": "theorem", "name": None,
            "label": f"Object {knowledge_id}", "source_key": f"key-{knowledge_id}", "difficulty": 40,
            "estimated_minutes": 1.3, "crystal_id": crystal_id, "crystal_default": True, "role": role, **extra}


def book_rows(**options):
    return Rows(
        sections=[section(1802, None, "002", "2 Connectedness", 1.5, 27.4),
                  section(1801, None, "001", "1 Topological spaces", None, 102.15)],
        # Book order, as the query returns it: 3 before 1.
        objects=[obj(3, 70), obj(1, 71), obj(2, 70), obj(4, 72, role=None)],
        edges=[
            {"relation_type": "dependency", "source_knowledge_id": 3, "target_knowledge_id": 2},
            {"relation_type": "dependency", "source_knowledge_id": 1, "target_knowledge_id": 2},
            {"relation_type": "dependency", "source_knowledge_id": 1, "target_knowledge_id": 99},  # 99 is inactive
            {"relation_type": "supports", "source_knowledge_id": 4, "target_knowledge_id": 3},
        ],
        **options,
    )


def test_the_answer_holds_sections_objects_relations_and_shared_crystals():
    built = book_read.build(book_rows(), 18)
    answer = json.loads(built.body)
    assert answer == built.answer
    assert set(answer) == {"format", "version", "grimoire_id", "graph_capability", "counts",
                           "sections", "objects", "relations", "crystals"}
    assert answer["format"] == 1 and answer["grimoire_id"] == 18
    assert answer["graph_capability"] == "semantic_relations"
    assert answer["sections"] == [
        {"id": 1801, "parent_id": None, "number": "001", "name": "1 Topological spaces", "depth": 0,
         "minutes_own": None, "minutes_whole": 102.15},
        {"id": 1802, "parent_id": None, "number": "002", "name": "2 Connectedness", "depth": 0,
         "minutes_own": 1.5, "minutes_whole": 27.4},
    ]
    assert [row["id"] for row in answer["objects"]] == [3, 1, 2, 4]  # the query's order, kept
    assert answer["objects"][0] == obj(3, 70)
    assert answer["objects"][3]["role"] is None
    assert answer["relations"] == {"dependency": [[1, 2], [3, 2]], "supports": [[4, 3]]}
    assert answer["crystals"] == [{"id": 70, "members": [3, 2]}]  # members in book order; 71 and 72 hold one
    assert answer["counts"] == {"sections": 2, "objects": 4, "shared_crystals": 1,
                                "relations": {"dependency": 2, "supports": 1}}


def test_a_book_without_relations_has_empty_relations():
    rows = book_rows()
    rows.edges = []
    answer = book_read.build(rows, 18).answer
    assert answer["relations"] == {} and answer["counts"]["relations"] == {}


def test_a_missing_book_cannot_be_built():
    with pytest.raises(LookupError):
        book_read.build(Rows(book=False), 18)
    with pytest.raises(LookupError):
        book_read.build_game(Rows(book=False), 18)


# --- the game's answer (0.0.16) --------------------------------------------------------------

UPLOADED = datetime(2026, 11, 12, 0, 0, 0, 123456, tzinfo=timezone.utc)


def figure(knowledge_id, image, storage_key, **extra):
    row = {"knowledge_id": knowledge_id, "source_image_id": image, "semantic_context_name": f"Figure {image}",
           "storage_key": storage_key, "url": f"https://bucket.example/{image}.png", "metadata": {"page": 4},
           "updated_at": UPLOADED}
    row.update(extra)
    return row


def scan(knowledge_id, image, page, printed, **extra):
    row = {"knowledge_id": knowledge_id, "source_image_id": image, "storage_key": f"books/18/pages/{image}.jpg",
           "url": "", "metadata": {"page": page, "printed_page": printed}, "updated_at": UPLOADED}
    row.update(extra)
    return row


def game_rows(**options):
    rows = book_rows(**options)
    rows.texts = [
        {"id": 1, "statement": r"Let $X$ be a space.", "working": r"Take $U \\subseteq X$.", "working_summary": "Open."},
        {"id": 2, "statement": "A statement.", "working": None, "working_summary": None},
        {"id": 3, "statement": "Three.", "working": "", "working_summary": ""},
        {"id": 4, "statement": "Four.", "working": "w", "working_summary": None},
    ]
    rows.figures = [
        figure(1, "fig-2", "books/18/images/fig 2.png"),
        figure(1, "fig-7", "", metadata={"page": "iv"}),  # no storage key: the stored url stays
        figure(3, "fig-2", "books/18/images/fig 2.png", semantic_context_name=None, metadata={"page": True},
               updated_at=datetime(2026, 11, 12, 1, 2, 3)),  # a naive time is UTC
    ]
    rows.pages = [
        scan(3, "p-012", 12, "4"), scan(3, "p-013", 13, 5),
        scan(1, "p-012", 12, "4"),
        scan(4, "p-099", None, ["x"], metadata={"page": "99"}),
    ]
    return rows


def test_the_game_answer_is_the_web_demos_with_texts_figures_and_pages():
    rows = game_rows()
    game = book_read.build_game(rows, 18).answer
    web = book_read.build(book_rows(), 18).answer
    assert set(game) == set(web) | {"pages"}
    for key in ("format", "grimoire_id", "graph_capability", "sections", "relations", "crystals"):
        assert game[key] == web[key], key
    added = {"statement", "working", "working_summary", "figures", "pages"}
    assert [item["id"] for item in game["objects"]] == [3, 1, 2, 4]  # the Web Demo's order
    for item, plain in zip(game["objects"], web["objects"]):
        assert set(item) == set(plain) | added
        assert {key: item[key] for key in plain} == plain
    assert game["counts"] == {**web["counts"], "figures": 3, "pages": 3}

    by_id = {item["id"]: item for item in game["objects"]}
    assert (by_id[1]["statement"], by_id[1]["working"], by_id[1]["working_summary"]) == (
        r"Let $X$ be a space.", r"Take $U \\subseteq X$.", "Open.")
    assert by_id[2]["working"] == "" and by_id[2]["working_summary"] is None
    assert by_id[3]["working_summary"] == ""  # as stored
    assert by_id[1]["figures"] == [
        {"image": "fig-2", "url": "/api/v1/storage/books/18/images/fig%202.png", "caption": "Figure fig-2",
         "page": 4, "updated_at": "2026-11-12T00:00:00Z"},
        {"image": "fig-7", "url": "https://bucket.example/fig-7.png", "caption": "Figure fig-7",
         "page": None, "updated_at": "2026-11-12T00:00:00Z"},
    ]
    assert by_id[3]["figures"] == [
        {"image": "fig-2", "url": "/api/v1/storage/books/18/images/fig%202.png", "caption": None,
         "page": None, "updated_at": "2026-11-12T01:02:03Z"},
    ]
    assert by_id[2]["figures"] == [] and by_id[2]["pages"] == []
    assert by_id[3]["pages"] == ["p-012", "p-013"] and by_id[1]["pages"] == ["p-012"]
    assert game["pages"] == {
        "p-012": {"url": "/api/v1/storage/books/18/pages/p-012.jpg", "page": 12, "printed_page": "4",
                  "updated_at": "2026-11-12T00:00:00Z"},
        "p-013": {"url": "/api/v1/storage/books/18/pages/p-013.jpg", "page": 13, "printed_page": 5,
                  "updated_at": "2026-11-12T00:00:00Z"},
        "p-099": {"url": "/api/v1/storage/books/18/pages/p-099.jpg", "page": None, "printed_page": None,
                  "updated_at": "2026-11-12T00:00:00Z"},
    }


def test_the_game_answer_reads_texts_figures_and_pages_with_one_query_each():
    rows = game_rows()
    book_read.build_game(rows, 18)
    queries = [(sql, params) for sql, params in rows.statements]
    assert len(queries) == 7  # the book, sections, objects, relations; texts, figures, pages
    texts, figures, pages = queries[4:]
    assert "lk.statement" in texts[0] and texts[1] == (18,)
    assert "link_type = 'figure'" in figures[0] and figures[1] == (18, 18)
    assert "b.knowledge_id IN" in figures[0]  # a figure linked before migration 012
    assert "link_type = 'page'" in pages[0] and pages[1] == (18,)
    for sql, _ in queries[4:]:
        assert "k.is_active" in sql
    assert "bi.is_active" in figures[0] and "bi.is_active" in pages[0]


def test_a_book_without_objects_has_an_empty_game_answer():
    rows = Rows(sections=[section(1801, None, "001", "1 Topological spaces")])
    answer = book_read.build_game(rows, 18).answer
    assert answer["objects"] == [] and answer["pages"] == {} and answer["relations"] == {}
    assert answer["counts"] == {"sections": 1, "objects": 0, "shared_crystals": 0, "relations": {},
                                "figures": 0, "pages": 0}


def test_the_game_answers_version_moves_with_an_images_time():
    first = book_read.build_game(game_rows(), 18)
    assert book_read.build_game(game_rows(), 18).body_gzip == first.body_gzip
    later = game_rows()
    later.pages = [dict(row, updated_at=datetime(2026, 11, 13, tzinfo=timezone.utc)) for row in later.pages]
    assert book_read.build_game(later, 18).version != first.version


def test_the_game_row_is_written_to_its_own_table_in_its_own_savepoint():
    rows = game_rows()
    result = book_read.refresh(rows, 18, book_read.GAME)
    assert result.status == "written"
    assert rows.ran("INSERT INTO book_game_read") and not rows.ran("INSERT INTO book_read ")
    assert [sql for sql, _ in rows.statements if "SAVEPOINT" in sql] == [
        "SAVEPOINT book_game_read_build", "RELEASE SAVEPOINT book_game_read_build",
    ]
    again = game_rows(stored_game={"format": 1, "version": result.built.version})
    assert book_read.refresh(again, 18, book_read.GAME).status == "unchanged"
    assert not again.ran("INSERT INTO book_game_read")


def test_both_rows_are_rebuilt_and_a_failed_game_build_removes_only_its_row(caplog):
    rows = game_rows(fail="lk.statement", failure="no texts")
    with caplog.at_level("WARNING", logger="app.services.book_read"):
        results = book_read.refresh_all(rows, 18)
    assert list(results) == ["book_read", "book_game_read"]
    assert results["book_read"].status == "written"
    assert results["book_game_read"].status == "failed" and results["book_game_read"].error == "no texts"
    assert rows.ran("INSERT INTO book_read ") and not rows.ran("INSERT INTO book_game_read")
    assert rows.ran("DELETE FROM book_game_read") == [(18,)] and not rows.ran("DELETE FROM book_read ")
    [record] = [record for record in caplog.records if record.name == "app.services.book_read"]
    assert record.getMessage().startswith("Game whole-book read of book 18 failed")


def test_a_check_that_cannot_build_reports_a_failure_and_lets_the_other_row_go_on():
    rows = game_rows(fail="lk.statement", failure="no texts")
    assert book_read.check(rows, 18, book_read.GAME).status == "failed"
    assert [sql for sql, _ in rows.statements if "SAVEPOINT" in sql] == [
        "SAVEPOINT book_game_read_check", "ROLLBACK TO SAVEPOINT book_game_read_check",
        "RELEASE SAVEPOINT book_game_read_check",
    ]
    assert book_read.check(game_rows(), 18, book_read.GAME).status == "missing"


def test_only_the_two_rows_are_known():
    with pytest.raises(ValueError):
        book_read.stored(Rows(), 18, "character")


def test_a_rebuild_writes_a_new_version_and_nothing_for_the_same_one():
    rows = book_rows()
    result = book_read.refresh(rows, 18)
    assert result.status == "written"
    insert = rows.ran("INSERT INTO book_read")
    assert insert and insert[0][:3] == (18, 1, result.built.version)
    assert insert[0][4:] == (len(result.built.body), 4)
    assert [sql for sql, _ in rows.statements if "SAVEPOINT" in sql] == [
        "SAVEPOINT book_read_build", "RELEASE SAVEPOINT book_read_build",
    ]
    assert result.receipt() == {"format": 1, "version": result.built.version,
                                "raw_bytes": len(result.built.body), "gzip_bytes": len(result.built.body_gzip)}

    again = book_rows(stored={"format": 1, "version": result.built.version})
    assert book_read.refresh(again, 18).status == "unchanged"
    assert not again.ran("INSERT INTO book_read")

    older_format = book_rows(stored={"format": 0, "version": result.built.version})
    assert book_read.refresh(older_format, 18).status == "written"


def test_a_failed_build_deletes_the_row_and_lets_the_transaction_go_on():
    rows = book_rows(fail="FROM knowledge_graph_edge")
    result = book_read.refresh(rows, 18)
    assert result.status == "failed" and result.built is None
    assert result.error.startswith("the build broke") and len(result.error) == 500
    assert result.receipt() == {"error": result.error}
    assert [sql for sql, _ in rows.statements if "SAVEPOINT" in sql or "book_read" in sql] == [
        "SAVEPOINT book_read_build",
        "ROLLBACK TO SAVEPOINT book_read_build",
        "DELETE FROM book_read WHERE grimoire_id = %s",
        "RELEASE SAVEPOINT book_read_build",
    ]


def test_a_failed_build_reports_one_line_and_logs_it(caplog):
    rows = book_rows(fail="FROM knowledge_graph_edge",
                     failure="injected failure\nCONTEXT:  PL/pgSQL function f() line 1 at RAISE\n")
    with caplog.at_level("WARNING", logger="app.services.book_read"):
        result = book_read.refresh(rows, 18)
    assert result.error == "injected failure CONTEXT: PL/pgSQL function f() line 1 at RAISE"
    assert result.receipt() == {"error": result.error}
    [record] = [record for record in caplog.records if record.name == "app.services.book_read"]
    assert record.levelname == "WARNING"
    assert "book 18" in record.getMessage() and result.error in record.getMessage()


def test_one_line_collapses_whitespace_and_cuts():
    assert book_read.one_line("a\n\tb  c\n") == "a b c"
    assert book_read.one_line("x" * 600) == "x" * 500
    assert book_read.one_line("y " * 300, 200) == ("y " * 100)[:200]
    assert book_read.one_line(KeyError()) == "KeyError"


def test_the_lock_is_per_book():
    rows = Rows()
    book_read.lock(rows, 18)
    assert rows.statements == [("SELECT pg_advisory_xact_lock(hashtext(%s), %s)", ("theumst.book_read", 18))]


@pytest.mark.parametrize(("stored", "status"), [
    (None, "missing"), ({"format": 0, "version": "x"}, "missing"), ({"format": 1, "version": "x"}, "stale"),
])
def test_a_check_writes_nothing(stored, status):
    rows = book_rows(stored=stored)
    assert book_read.check(rows, 18).status == status
    assert not [sql for sql, _ in rows.statements if sql.startswith(("INSERT", "UPDATE", "DELETE"))]


def test_ingestion_and_submission_lock_then_rebuild_inside_their_transactions():
    from inspect import getsource

    from app.services import book_ingestion, knowledge

    ingest = getsource(book_ingestion.ingest_book_archive)
    assert ingest.index("_upsert_book(") < ingest.index("book_read.lock(") < ingest.index("_deactivate_book_state(")
    assert ingest.index("apply_graph_sidecar(") < ingest.index("book_read.refresh_all(") < ingest.index(
        "_stale_embedding_points(")
    assert ingest.index("_store_images(") < ingest.index("_finalize_images(")
    assert '"book_read": book_read_result.receipt()' in ingest
    assert '"book_game_read": book_game_read_result.receipt()' in ingest
    submit = getsource(knowledge.submit_knowledge)
    assert submit.index("_resolve_book(") < submit.index("book_read.lock(") < submit.index("_resolve_section(")
    assert submit.index("_queue_embeddings(") < submit.index("book_read.refresh_all(") < submit.index(
        "_index_pending_embeddings(")


def test_the_game_row_is_rebuilt_once_the_images_are_active_again(monkeypatch):
    """_deactivate_book_state turns a book's images off in the upload's transaction, so the game's
    answer built there names no figure or scan. _finalize_images takes the lock, writes the image rows
    and rebuilds the game's row in its own transaction, whether the upload had images or not."""
    from app.services import book_ingestion

    calls = []

    @contextmanager
    def recorded_transaction():
        calls.append("transaction")
        yield None, "cursor"

    def write_images(cur, images, grimoire_id):
        calls.append(("images", len(images)))
        return {"figure": 2, "page": 1}

    rebuilt = book_read.BookReadResult("written")

    def refresh(cur, grimoire_id, read):
        calls.append(("refresh", grimoire_id, read))
        return rebuilt

    monkeypatch.setattr(book_ingestion, "transaction", recorded_transaction)
    monkeypatch.setattr(book_read, "lock", lambda cur, grimoire_id: calls.append(("lock", grimoire_id)))
    monkeypatch.setattr(book_ingestion, "_write_image_rows", write_images)
    monkeypatch.setattr(book_read, "refresh", refresh)
    assert book_ingestion._finalize_images([{"source_image_id": "a"}], 18) == ({"figure": 2, "page": 1}, rebuilt)
    assert calls == ["transaction", ("lock", 18), ("images", 1), ("refresh", 18, "book_game_read")]
    calls.clear()
    book_ingestion._finalize_images([], 18)
    assert calls == ["transaction", ("lock", 18), ("images", 0), ("refresh", 18, "book_game_read")]


# --- the route ----------------------------------------------------------------------------

def demo_user():
    return {"user_id": 2, "username": "reader", "email": "reader@example.invalid", "alias": None,
            "description": None, "authority_type": "betatester", "access_points": ["demo", "profile"]}


class Database:
    """Answers the route's queries by their text, and keeps every statement."""

    def __init__(self, built, *, user=None, visible=True, row=True, format=1):
        self.built, self.user, self.visible, self.row, self.format = built, user, visible, row, format
        self.statements: list[tuple[str, object]] = []

    @contextmanager
    def transaction(self):
        yield None, self

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))

    def fetchone(self):
        sql = self.statements[-1][0]
        if "FROM web_session s" in sql:
            return dict(self.user) if self.user else None
        if "LEFT JOIN book_read br" in sql:
            if self.visible is None:
                return None
            return {"visible": self.visible, "format": self.format if self.row else None,
                    "version": self.built.version if self.row else None}
        if sql.startswith("SELECT version, body_gzip FROM book_read"):
            return {"version": self.built.version, "body_gzip": memoryview(self.built.body_gzip)} if self.row else None
        raise AssertionError(f"unexpected query: {sql}")


@pytest.fixture
def route(monkeypatch):
    rows = book_rows()
    # Enough distinct labels that the stored gzip is over GZipMiddleware's 1,000-byte minimum,
    # so the middleware would compress it again if it did not leave it alone.
    rows.objects = rows.objects + [
        obj(100 + n, 200 + n, label=hashlib.sha256(str(n).encode()).hexdigest()) for n in range(60)
    ]
    built = book_read.build(rows, 18)
    assert len(built.body_gzip) > 2_000
    state = Database(built, user=demo_user())
    monkeypatch.setattr(dependencies, "transaction", lambda: state.transaction())
    monkeypatch.setattr(demo, "transaction", lambda: state.transaction())
    state.client = TestClient(create_app(initialize_services=False))
    state.cookie = {"Cookie": f"{get_settings().cookie_name}=session-token"}
    state.url = ROUTE.format(grimoire_id=18)
    return state


def assert_cache_headers(response, version):
    assert response.headers["etag"] == f'"{version}"'
    assert response.headers["cache-control"] == TWO_WEEKS
    vary = [token.strip() for token in response.headers["vary"].split(",")]
    assert vary[:3] == ["Authorization", "Cookie", "Accept-Encoding"]
    # On an uncompressed answer of 1,000 bytes or more GZipMiddleware adds Accept-Encoding again,
    # as on the Atlas route. The tokens, which are all a cache reads, stay the same.
    assert set(vary) == {"Authorization", "Cookie", "Accept-Encoding"}


def test_the_route_is_registered_as_a_read():
    application = create_app(initialize_services=False)
    methods = {method for route in application.routes if getattr(route, "path", "") == ROUTE
               for method in route.methods}
    assert methods == {"GET"}


def test_without_a_session_the_route_answers_401_and_keeps_nothing(route):
    response = route.client.get(route.url)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert response.headers["cache-control"] == "no-store"
    assert not [sql for sql, _ in route.statements if "book_read" in sql]


def test_an_account_without_web_demo_access_gets_403(route):
    route.user = {**demo_user(), "authority_type": "user", "access_points": ["profile", "api-keys"]}
    response = route.client.get(route.url, headers=route.cookie)
    assert response.status_code == 403
    assert response.json() == {"detail": "Access to demo is not permitted"}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("visible", [None, False])
def test_a_missing_or_hidden_book_is_not_found(route, visible):
    route.visible = visible
    response = route.client.get(route.url, headers=route.cookie)
    assert response.status_code == 404
    assert response.json() == {"detail": "Demo grimoire not found", "code": "book_not_found"}
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers


@pytest.mark.parametrize(("row", "format"), [(False, 1), (True, 2)])
def test_a_book_without_its_read_in_this_format_answers_409(route, row, format):
    route.row, route.format = row, format
    response = route.client.get(route.url, headers=route.cookie)
    assert response.status_code == 409
    assert response.json() == {"detail": "This book's whole read has not been computed yet",
                               "code": "book_read_not_computed"}
    assert response.headers["cache-control"] == "no-store"


def test_a_client_that_accepts_gzip_gets_the_stored_bytes_in_one_layer(route):
    headers = {**route.cookie, "Accept-Encoding": "gzip, deflate, br"}
    with route.client.stream("GET", route.url, headers=headers) as response:
        raw = b"".join(response.iter_raw())
    assert response.status_code == 200
    assert raw == route.built.body_gzip  # GZipMiddleware left it alone
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["content-length"] == str(len(route.built.body_gzip))
    assert response.headers["content-type"] == "application/json"
    assert_cache_headers(response, route.built.version)
    assert json.loads(gzip.decompress(raw)) == route.built.answer


@pytest.mark.parametrize("accept", ["identity", "gzip;q=0", "gzip;q=0, *", "br", ""])
def test_a_client_that_refuses_gzip_gets_the_json_itself(route, accept):
    with route.client.stream("GET", route.url, headers={**route.cookie, "Accept-Encoding": accept}) as response:
        raw = b"".join(response.iter_raw())
    assert response.status_code == 200
    if response.headers.get("content-encoding") == "gzip":
        # Starlette's GZipMiddleware looks only for the word gzip in the header, and compresses a body
        # of 1,000 bytes or more itself, as on every other route. That is still one layer.
        assert "gzip" in accept
        raw = gzip.decompress(raw)
    assert raw == route.built.body
    assert_cache_headers(response, route.built.version)


@pytest.mark.parametrize("value", [
    '"{v}"', 'W/"{v}"', ' W/ "{v}" ', '"other", "{v}"', '"other",W/"{v}"', "*",
])
def test_a_matching_if_none_match_answers_304_without_the_body(route, value):
    headers = {**route.cookie, "If-None-Match": value.format(v=route.built.version)}
    response = route.client.get(route.url, headers=headers)
    assert response.status_code == 304
    assert response.content == b""
    assert_cache_headers(response, route.built.version)
    assert not [sql for sql, _ in route.statements if "body_gzip" in sql]


@pytest.mark.parametrize("value", ['"other"', "{v}", '"{v}x"', ""])
def test_another_tag_gets_the_whole_answer(route, value):
    headers = {**route.cookie, "If-None-Match": value.format(v=route.built.version)}
    response = route.client.get(route.url, headers=headers)
    assert response.status_code == 200
    assert response.json() == route.built.answer


def test_the_route_writes_nothing(route):
    route.client.get(route.url, headers=route.cookie)
    assert not [sql for sql, _ in route.statements if sql.startswith(("INSERT", "UPDATE", "DELETE"))]


def test_a_non_integer_id_gets_fastapis_422(route):
    assert route.client.get("/api/demo/grimoires/eighteen/book-read", headers=route.cookie).status_code == 422


@pytest.mark.parametrize(("header", "allowed"), [
    ("gzip", True), ("GZIP", True), ("x-gzip", True), ("deflate, gzip;q=0.5", True), ("*", True),
    ("identity", False), ("", False), (None, False), ("gzip;q=0", False), ("gzip;q=0.0, *", False),
    ("*;q=0", False), ("br, *;q=0.1", True), ("gzip;q=nonsense", False),
])
def test_accept_encoding_is_read_with_its_qualities(header, allowed):
    assert book_read.accepts_gzip(header) is allowed


# --- migration 016 ---------------------------------------------------------------------------

def table(text: str) -> str:
    match = re.search(r"CREATE TABLE IF NOT EXISTS book_read \((.*?)\n\);", text, re.DOTALL)
    assert match
    return match.group(1)


def test_migration_016_and_schema_make_the_same_table():
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    assert table(migration) == table(SCHEMA)
    columns = [line.strip().split()[0] for line in table(migration).strip().splitlines()]
    assert columns == ["grimoire_id", "format", "version", "body_gzip", "raw_bytes", "object_count", "built_at"]
    assert "REFERENCES grimoire(grimoire_id) ON DELETE CASCADE" in table(migration)
    statements = [line for line in migration.splitlines() if line.strip() and not line.startswith("--")]
    assert statements[0] == "CREATE TABLE IF NOT EXISTS book_read ("  # one statement, and no rows


def test_the_pin_is_the_sha256_of_the_file_as_git_checks_it_out():
    data = MIGRATION_PATH.read_bytes()
    assert b"\r" not in data  # .gitattributes keeps *.sql at LF on every machine
    assert hashlib.sha256(data).hexdigest() == BOOK_READ_MIGRATION.sha256
    assert reviewed_migrations.REVIEWED_MIGRATIONS[-2] is BOOK_READ_MIGRATION
    assert reviewed_migrations.REVIEWED_MIGRATIONS[-3].key == "character_lease_install_v1"


def test_the_readiness_marker_is_the_table():
    assert [(marker.kind, marker.name) for marker in BOOK_READ_MIGRATION.exclusive_markers] == [
        ("relation", "public.book_read"),
    ]
    assert not BOOK_READ_MIGRATION.shared_markers


# --- migration 017 ---------------------------------------------------------------------------

def game_table(text: str) -> str:
    match = re.search(r"CREATE TABLE IF NOT EXISTS book_game_read \((.*?)\n\);", text, re.DOTALL)
    assert match
    return match.group(1)


def test_migration_017_and_schema_make_the_same_table_as_book_reads():
    migration = GAME_MIGRATION_PATH.read_text(encoding="utf-8")
    assert game_table(migration) == game_table(SCHEMA) == table(SCHEMA)
    statements = [line for line in migration.splitlines() if line.strip() and not line.startswith("--")]
    assert statements[0] == "CREATE TABLE IF NOT EXISTS book_game_read ("  # one statement, and no rows


def test_017_is_pinned_after_016_with_its_table_as_the_marker():
    data = GAME_MIGRATION_PATH.read_bytes()
    assert b"\r" not in data
    assert hashlib.sha256(data).hexdigest() == BOOK_GAME_READ_MIGRATION.sha256
    assert reviewed_migrations.REVIEWED_MIGRATIONS[-1] is BOOK_GAME_READ_MIGRATION
    assert BOOK_GAME_READ_MIGRATION.filename == "017_book_game_read.sql"
    assert [(marker.kind, marker.name) for marker in BOOK_GAME_READ_MIGRATION.exclusive_markers] == [
        ("relation", "public.book_game_read"),
    ]
    assert not BOOK_GAME_READ_MIGRATION.shared_markers


# --- the operator command ------------------------------------------------------------------

def result(status, built=None, error=None):
    return book_read.BookReadResult(status, built=built, error=error)


@pytest.fixture
def command(monkeypatch):
    built = book_read.build(book_rows(), 18)
    game_built = book_read.build_game(game_rows(), 18)
    outcomes: dict[int, tuple[book_read.BookReadResult, book_read.BookReadResult]] = {}
    calls: list[tuple[int, bool]] = []

    def one(grimoire_id, check):
        calls.append((grimoire_id, check))
        return list(zip(book_read.READS, outcomes[grimoire_id], (0.01, 0.02)))

    monkeypatch.setattr(build_book_reads, "_one", one)
    monkeypatch.setattr(build_book_reads, "_book_ids",
                        lambda requested: (sorted(outcomes) if not requested else
                                           sorted(set(requested) & set(outcomes)),
                                           sorted(set(requested) - set(outcomes))))

    def run(*args, **options):
        out = io.StringIO()
        code = build_book_reads.run(*args, out=out, **options)
        return code, out.getvalue().splitlines()

    return built, game_built, outcomes, calls, run


def test_the_command_prints_a_line_per_row_and_a_total(command):
    built, game_built, outcomes, calls, run = command
    outcomes.update({
        8: (result("written", built), result("written", game_built)),
        18: (result("unchanged", built), result("written", game_built)),
        21: (result("failed", error="boom"), result("failed", error="boom")),
    })
    code, lines = run()
    assert code == 1
    assert lines[0] == "book_read format 1; book_game_read format 1"
    assert re.fullmatch(
        r"book    8  book_read       objects     4  sections    2  dependency     2  supports     1  crystals    1"
        r"  raw +[\d,]+  gzip +[\d,]+  " + built.version[:12] + r"  written    0\.01 s",
        lines[1],
    ), lines[1]
    assert re.fullmatch(
        r"book    8  book_game_read  objects     4  figures     3  pages     3"
        r"  raw +[\d,]+  gzip +[\d,]+  " + game_built.version[:12] + r"  written    0\.02 s",
        lines[2],
    ), lines[2]
    assert lines[3].startswith("book   18  book_read       objects     4  ") and "  unchanged  " in lines[3]
    assert lines[4].startswith("book   18  book_game_read  objects     4  ") and "  written  " in lines[4]
    assert lines[5] == "book   21  book_read       failed: boom"
    assert lines[6] == "book   21  book_game_read  failed: boom"
    assert re.fullmatch(r"3 books: book_read 1 written, 1 unchanged, 1 failed; "
                        r"book_game_read 2 written, 0 unchanged, 1 failed; [\d,]+ bytes gzipped in all; \d+\.\d s",
                        lines[7]), lines[7]
    assert len(lines) == 8
    assert calls == [(8, False), (18, False), (21, False)]
    for line in lines[1:5]:
        assert int(line.split()[1]) in (8, 18) and line.split()[-3] in ("written", "unchanged")


def test_the_command_exits_0_when_nothing_failed(command):
    built, game_built, outcomes, _, run = command
    outcomes.update({8: (result("written", built), result("written", game_built)),
                     18: (result("unchanged", built), result("unchanged", game_built))})
    assert run()[0] == 0


def test_a_failed_game_row_alone_fails_the_run(command):
    built, _, outcomes, _, run = command
    outcomes.update({8: (result("written", built), result("failed", error="no texts"))})
    code, lines = run()
    assert code == 1 and lines[2] == "book    8  book_game_read  failed: no texts"


def test_a_check_that_finds_a_stale_or_missing_row_exits_2(command):
    built, game_built, outcomes, calls, run = command
    outcomes.update({
        8: (result("current", built), result("current", game_built)),
        18: (result("current", built), result("stale", game_built)),
        19: (result("missing", built), result("current", game_built)),
    })
    code, lines = run(check=True)
    assert code == 2
    assert calls == [(8, True), (18, True), (19, True)]
    assert lines[-1].startswith("3 books: book_read 2 current, 0 stale, 1 missing, 0 failed; "
                                "book_game_read 2 current, 1 stale, 0 missing, 0 failed;")
    outcomes.update({18: (result("current", built), result("current", game_built)),
                     19: (result("current", built), result("current", game_built))})
    assert run(check=True)[0] == 0


def test_a_multi_line_failure_stays_on_its_book_line(command):
    built, game_built, outcomes, _, run = command
    failure = result("failed", error="injected book_read failure\nCONTEXT:  PL/pgSQL function f() line 1\n")
    outcomes.update({4: (failure, failure), 8: (result("written", built), result("written", game_built))})
    code, lines = run()
    assert code == 1
    assert lines[1] == "book    4  book_read       failed: injected book_read failure CONTEXT: PL/pgSQL function f() line 1"
    assert lines[3].startswith("book    8  book_read       objects")
    assert len(lines) == 6


def test_one_book_builds_both_rows_under_its_lock(monkeypatch):
    cursor = game_rows()

    @contextmanager
    def one_transaction():
        yield None, cursor

    monkeypatch.setattr(build_book_reads, "transaction", one_transaction)
    rows = build_book_reads._one(18, False)
    assert [(read, outcome.status) for read, outcome, _ in rows] == [("book_read", "written"), ("book_game_read", "written")]
    assert cursor.statements[0] == ("SELECT pg_advisory_xact_lock(hashtext(%s), %s)", ("theumst.book_read", 18))

    cursor = game_rows(fail="lk.statement", failure="no texts")
    statuses = [(read, outcome.status) for read, outcome, _ in build_book_reads._one(18, True)]
    assert statuses == [("book_read", "missing"), ("book_game_read", "failed")]
    assert cursor.statements[0] == ("SET TRANSACTION READ ONLY", None)
    assert not [sql for sql, _ in cursor.statements if sql.startswith(("INSERT", "UPDATE", "DELETE"))]


def test_an_exception_in_one_book_is_one_line_on_both_rows(monkeypatch):
    @contextmanager
    def broken_transaction():
        raise RuntimeError("server closed the connection\nunexpectedly\n")
        yield  # pragma: no cover

    monkeypatch.setattr(build_book_reads, "transaction", broken_transaction)
    rows = build_book_reads._one(8, False)
    assert [read for read, _, _ in rows] == ["book_read", "book_game_read"]
    for _, outcome, _ in rows:
        assert outcome.status == "failed" and outcome.error == "server closed the connection unexpectedly"


def test_an_unknown_book_is_a_failure(command):
    built, game_built, outcomes, _, run = command
    outcomes.update({8: (result("written", built), result("written", game_built))})
    code, lines = run([8, 404])
    assert code == 1
    assert "book  404  failed: no such book" in lines
    assert lines[-1].startswith("2 books: book_read 1 written, 0 unchanged, 1 failed; "
                                "book_game_read 1 written, 0 unchanged, 1 failed;")


def test_the_command_reads_its_options(monkeypatch):
    seen = {}

    def fake_run(requested, *, check):
        seen.update(requested=requested, check=check)
        return 0

    monkeypatch.setattr(build_book_reads, "run", fake_run)
    assert build_book_reads.main(["--book", "8", "--book", "18", "--check"]) == 0
    assert seen == {"requested": [8, 18], "check": True}
    assert build_book_reads.main([]) == 0
    assert seen == {"requested": [], "check": False}


def test_the_wrapper_runs_only_the_command_and_removes_its_key_copy():
    script = (ROOT / "dev/sh/agent_build_book_reads.sh").read_text(encoding="utf-8")
    assert "exec -T \\\n        backend python -m scripts.build_book_reads$COMMAND_ARGS" in script
    assert "trap cleanup_runtime_key EXIT" in script
    assert "remote_upload" not in script and "remote_full_deploy" not in script  # their traps replace this one
    assert '*) echo "Unknown option: $1" >&2; exit 2 ;;' in script
    assert "''|*[!0-9]*) echo \"--book needs a numeric grimoire id\"" in script
