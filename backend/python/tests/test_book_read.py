"""The whole-book read (0.0.15): its answer, the route's answers and headers, migration 016,
and the operator command, with scripted stand-ins for PostgreSQL.

These establish the shape and order of the answer built from given rows, the order of the
route's checks, its caching headers, that one gzip layer reaches the client, and the
command's lines and exit codes. test_book_read_postgres.py checks the same against
PostgreSQL, through ingestion and the application.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
from contextlib import contextmanager
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
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
BOOK_READ_MIGRATION = next(
    migration for migration in reviewed_migrations.REVIEWED_MIGRATIONS if migration.key == "book_read_v1"
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
                 failure="the build broke " + "x" * 600):
        self.book, self.sections, self.objects, self.edges = book, sections, objects, edges
        self.stored, self.fail, self.failure = stored, fail, failure
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
        raise AssertionError(f"unexpected fetchone: {sql}")

    def fetchall(self):
        sql = self._last()
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
    assert ingest.index("apply_graph_sidecar(") < ingest.index("book_read.refresh(") < ingest.index(
        "_stale_embedding_points(")
    assert '"book_read": book_read_result.receipt()' in ingest
    submit = getsource(knowledge.submit_knowledge)
    assert submit.index("_resolve_book(") < submit.index("book_read.lock(") < submit.index("_resolve_section(")
    assert submit.index("_queue_embeddings(") < submit.index("book_read.refresh(") < submit.index(
        "_index_pending_embeddings(")


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
    assert demo._accepts_gzip(header) is allowed


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
    assert reviewed_migrations.REVIEWED_MIGRATIONS[-1] is BOOK_READ_MIGRATION
    assert reviewed_migrations.REVIEWED_MIGRATIONS[-2].key == "character_lease_install_v1"


def test_the_readiness_marker_is_the_table():
    assert [(marker.kind, marker.name) for marker in BOOK_READ_MIGRATION.exclusive_markers] == [
        ("relation", "public.book_read"),
    ]
    assert not BOOK_READ_MIGRATION.shared_markers


# --- the operator command ------------------------------------------------------------------

def result(status, built=None, error=None):
    return book_read.BookReadResult(status, built=built, error=error)


@pytest.fixture
def command(monkeypatch):
    built = book_read.build(book_rows(), 18)
    outcomes: dict[int, book_read.BookReadResult] = {}
    calls: list[tuple[int, bool]] = []

    def one(grimoire_id, check):
        calls.append((grimoire_id, check))
        return outcomes[grimoire_id]

    monkeypatch.setattr(build_book_reads, "_one", one)
    monkeypatch.setattr(build_book_reads, "_book_ids",
                        lambda requested: (sorted(outcomes) if not requested else
                                           sorted(set(requested) & set(outcomes)),
                                           sorted(set(requested) - set(outcomes))))

    def run(*args, **options):
        out = io.StringIO()
        code = build_book_reads.run(*args, out=out, **options)
        return code, out.getvalue().splitlines()

    return built, outcomes, calls, run


def test_the_command_prints_a_line_per_book_and_a_total(command):
    built, outcomes, calls, run = command
    outcomes.update({8: result("written", built), 18: result("unchanged", built), 21: result("failed", error="boom")})
    code, lines = run()
    assert code == 1
    assert lines[0] == "book_read format 1"
    assert re.fullmatch(
        r"book    8  objects     4  sections    2  dependency     2  supports     1  crystals    1"
        r"  raw +[\d,]+  gzip +[\d,]+  " + built.version[:12] + r"  written  +\d+\.\d\d s",
        lines[1],
    ), lines[1]
    assert lines[2].startswith("book   18  objects     4  ") and f"  {built.version[:12]}  unchanged  " in lines[2]
    assert lines[3] == "book   21  failed: boom"
    assert re.fullmatch(r"3 books: 1 written, 1 unchanged, 1 failed; [\d,]+ bytes gzipped in all; \d+\.\d s", lines[4])
    assert calls == [(8, False), (18, False), (21, False)]


def test_the_command_exits_0_when_nothing_failed(command):
    built, outcomes, _, run = command
    outcomes.update({8: result("written", built), 18: result("unchanged", built)})
    assert run()[0] == 0


def test_a_check_that_finds_a_stale_or_missing_book_exits_2(command):
    built, outcomes, calls, run = command
    outcomes.update({8: result("current", built), 18: result("stale", built), 19: result("missing", built)})
    code, lines = run(check=True)
    assert code == 2
    assert calls == [(8, True), (18, True), (19, True)]
    assert lines[-1].startswith("3 books: 1 current, 1 stale, 1 missing, 0 failed;")
    outcomes.update({18: result("current", built), 19: result("current", built)})
    assert run(check=True)[0] == 0


def test_a_multi_line_failure_stays_on_its_book_line(command):
    built, outcomes, _, run = command
    outcomes.update({
        4: result("failed", error="injected book_read failure\nCONTEXT:  PL/pgSQL function f() line 1\n"),
        8: result("written", built),
    })
    code, lines = run()
    assert code == 1
    assert lines[1] == "book    4  failed: injected book_read failure CONTEXT: PL/pgSQL function f() line 1"
    assert lines[2].startswith("book    8  objects")
    assert len(lines) == 4


def test_an_exception_in_one_book_is_one_line(monkeypatch):
    @contextmanager
    def broken_transaction():
        raise RuntimeError("server closed the connection\nunexpectedly\n")
        yield  # pragma: no cover

    monkeypatch.setattr(build_book_reads, "transaction", broken_transaction)
    outcome = build_book_reads._one(8, False)
    assert outcome.status == "failed" and outcome.error == "server closed the connection unexpectedly"


def test_an_unknown_book_is_a_failure(command):
    built, outcomes, _, run = command
    outcomes.update({8: result("written", built)})
    code, lines = run([8, 404])
    assert code == 1
    assert "book  404  failed: no such book" in lines


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
