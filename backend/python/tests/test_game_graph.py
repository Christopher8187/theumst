"""The game's graph routes (0.0.19) and their reads, over an in-memory graph; no database.

FakeGraph answers each GraphSource method from a small graph of three books, one of them hidden, as
SqlGraph answers it from PostgreSQL: active objects of visible books only. The service's logic (the
support component, detached proofs, the walk over crystals, the word budget, sections and book order)
runs on it unchanged. The SQL itself is checked for its visibility filter on a recording cursor; the
checks on theumst.com run each route once against the 28 books.
"""
from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import game
from app.routers import game_graph as graph_router
from app.services import game_graph
from app.services.game_graph import SqlGraph

R, M, HIDDEN = 18, 25, 40


class FakeGraph:
    """Books, sections, objects, crystals and arrows held in dictionaries."""

    def __init__(self):
        self.books: dict[int, dict] = {}
        self.sections_by_id: dict[int, dict] = {}
        self.objects_by_id: dict[int, dict] = {}
        self.edges: list[tuple[int, str, int, int]] = []
        self.scans: dict[int, tuple[list, object]] = {}
        self.calls: list[str] = []

    # building
    def book(self, grimoire_id, title, visible=True):
        self.books[grimoire_id] = {"title": title, "visible": visible}

    def sec(self, section_id, book, number, name, parent=None):
        self.sections_by_id[section_id] = {"section_id": section_id, "grimoire_id": book, "parent_section": parent,
                                           "section_number": number, "section_name": name}

    def obj(self, knowledge_id, book, section, type_, crystal, *, name="", label="", statement="s",
            working="", order=None, key=None, default=False, active=True):
        self.objects_by_id[knowledge_id] = {
            "knowledge_id": knowledge_id, "grimoire_id": book, "section_id": section, "type": type_,
            "crystal_id": crystal, "name": name, "label": label, "statement": statement, "working": working,
            "working_summary": "", "order": knowledge_id if order is None else order,
            "source_key": key or f"k{knowledge_id}", "default": default, "active": active,
        }

    def uses(self, user, *used):
        for item in used:
            self.edges.append((self.objects_by_id[user]["grimoire_id"], "dependency", item, user))

    def supports(self, supporter, supported):
        self.edges.append((self.objects_by_id[supporter]["grimoire_id"], "supports", supporter, supported))

    # reading
    def _visible(self, knowledge_id):
        row = self.objects_by_id.get(knowledge_id)
        return row is not None and row["active"] and self.books[row["grimoire_id"]]["visible"]

    def _row(self, knowledge_id, working=False):
        row = self.objects_by_id[knowledge_id]
        size = sum(1 for other in self.objects_by_id
                   if self._visible(other) and self.objects_by_id[other]["crystal_id"] == row["crystal_id"])
        out = {key: row[key] for key in ("knowledge_id", "source_key", "grimoire_id", "section_id", "label", "name",
                                         "statement", "type", "crystal_id")}
        out.update(book_title=self.books[row["grimoire_id"]]["title"], crystal_size=size)
        if working:
            out.update(working=row["working"], working_summary=row["working_summary"])
        return out

    def _book_order(self, grimoire_id):
        ids = [i for i, row in self.objects_by_id.items() if row["grimoire_id"] == grimoire_id and self._visible(i)]
        return sorted(ids, key=lambda i: (self.objects_by_id[i]["order"], i))

    def find(self, *, knowledge_id=None, source_key=None, grimoire_id=None):
        self.calls.append("find")
        hits = [i for i, row in self.objects_by_id.items() if self._visible(i) and (
            i == knowledge_id if knowledge_id is not None else
            row["source_key"] == source_key and (grimoire_id is None or row["grimoire_id"] == grimoire_id))]
        return [self._row(i) for i in sorted(hits, key=lambda i: (self.objects_by_id[i]["grimoire_id"], i))][:2]

    def objects(self, ids, *, working=False):
        self.calls.append("objects")
        return {i: self._row(i, working) for i in ids if self._visible(i)}

    def arrows(self, ends, relation, side):
        self.calls.append(f"arrows:{relation}:{side}")
        out = []
        for book, end in ends:
            for edge_book, kind, source, target in self.edges:
                if edge_book != book or kind != relation:
                    continue
                here, other = (target, source) if side == "in" else (source, target)
                if here == end and self._visible(other):
                    row = self.objects_by_id[other]
                    out.append({"end": end, "other": other, "other_type": row["type"],
                                "other_crystal_id": row["crystal_id"], "grimoire_id": book})
        return sorted(out, key=lambda row: (row["end"], row["other"]))

    def positions(self, grimoire_id, ids):
        self.calls.append("positions")
        order = self._book_order(grimoire_id)
        return {i: order.index(i) + 1 for i in ids if i in order}, len(order)

    def window(self, grimoire_id, first, last):
        return self._book_order(grimoire_id)[first - 1:last]

    def section_objects(self, grimoire_id, section_id, limit):
        order = self._book_order(grimoire_id)
        return [(i, n) for n, i in enumerate(order, 1) if self.objects_by_id[i]["section_id"] == section_id][:limit]

    def sections(self, grimoire_id):
        return [dict(row) for row in self.sections_by_id.values() if row["grimoire_id"] == grimoire_id]

    def section(self, section_id):
        row = self.sections_by_id.get(section_id)
        if row is None or not self.books[row["grimoire_id"]]["visible"]:
            return None
        return {"section_id": section_id, "grimoire_id": row["grimoire_id"],
                "book_title": self.books[row["grimoire_id"]]["title"]}

    def members(self, crystal_ids):
        self.calls.append("members")
        rows = []
        for crystal_id in crystal_ids:
            ids = [i for i, row in self.objects_by_id.items() if row["crystal_id"] == crystal_id and self._visible(i)]
            ids.sort(key=lambda i: (self.objects_by_id[i]["grimoire_id"], self.objects_by_id[i]["order"], i))
            rows += [{"crystal_id": crystal_id, "knowledge_id": i, "grimoire_id": self.objects_by_id[i]["grimoire_id"],
                      "type": self.objects_by_id[i]["type"], "default": self.objects_by_id[i]["default"]} for i in ids]
        return rows

    def pages(self, knowledge_id):
        return self.scans.get(knowledge_id, ([], None))

    def match(self, source_keys):
        return [{"source_key": row["source_key"], "knowledge_id": i, "grimoire_id": row["grimoire_id"]}
                for i, row in sorted(self.objects_by_id.items())
                if row["source_key"] in source_keys and self._visible(i)]


def graph() -> FakeGraph:
    """Book 18 (the reader's), book 25 (another), book 40 (hidden).

    Book 18, in book order: 10 a definition; 11 a definition; 12 a supporting lemma supporting 13; 13 a
    theorem using 11 and 12; 14 a supporting exercise supporting 12 and using 11; fifteen remarks; 40 a
    reference; 31 a detached proof in another chapter using 10, 12 and 13, so proving 13.
    Book 25: 52 (crystal 9052, only here) uses 53 and 55; 53 uses 51; 51 is in 11's crystal; 55 is in
    40's crystal, which book 18 holds only as a reference; 50 shares 13's crystal.
    """
    g = FakeGraph()
    g.book(R, "Topological Spaces")
    g.book(M, "Topology (Munkres)")
    g.book(HIDDEN, "Hidden", visible=False)
    g.sec(100, R, "1", "Spaces")
    g.sec(101, R, "1", "Open sets", parent=100)
    g.sec(110, R, "2", "Connectedness")
    g.sec(111, R, "1", "Connected spaces", parent=110)
    g.sec(120, R, "3", "Proofs")
    g.sec(121, R, "1", "Detached proofs", parent=120)
    g.sec(200, M, "23", "Connected spaces")
    g.sec(400, HIDDEN, "1", "Hidden")
    g.obj(10, R, 101, "definition", 9010, name="Topology", label="Definition 1.1", statement="A topology is a family")
    g.obj(11, R, 111, "definition", 9011, name="Connected", label="Definition 2.1", statement="A space is connected")
    g.obj(12, R, 111, "supporting_lemma", 9012, name="Clopen lemma", statement="A clopen set", working="w12")
    g.obj(13, R, 111, "theorem", 9013, name="Images are connected", label="Proposition",
          statement="The image of a connected space is connected", working="*Proof.* w13")
    g.obj(14, R, 111, "supporting_exercise", 9014, name="Two point space", statement="Show it", working="w14")
    for n in range(15, 30):
        g.obj(n, R, 111, "remark", 9000 + n, statement="filler")
    g.obj(40, R, 111, "reference", 9054, name="Separation axiom", statement="See elsewhere", order=30)
    g.obj(31, R, 121, "detachedproof", 9031, name="Second proof", statement="Proves the proposition",
          working="w31", order=31)
    g.supports(12, 13)
    g.supports(14, 12)
    g.uses(13, 11, 12)
    g.uses(12, 10)
    g.uses(14, 11)
    g.uses(31, 10, 12, 13)
    g.uses(11, 10)
    g.obj(50, M, 200, "theorem", 9013, name="Theorem 23.5", statement="Continuous images", default=True, order=1)
    g.obj(51, M, 200, "definition", 9011, name="Connected", statement="No separation", order=2)
    g.obj(53, M, 200, "definition", 9053, name="Separation", statement="A pair of open sets", order=3)
    g.obj(55, M, 200, "definition", 9054, name="Hausdorff", statement="Points separate", order=4)
    g.obj(52, M, 200, "theorem", 9052, name="Lemma 23.2", statement="A connected subspace lies in one side",
          order=5)
    g.uses(52, 53, 55)
    g.uses(53, 51)
    g.uses(50, 51, 52)
    g.obj(60, HIDDEN, 400, "theorem", 9013, name="Hidden copy")
    return g


# --- the service ----------------------------------------------------------------------------

def test_load_gives_the_support_component_detached_proof_and_dependencies():
    g = graph()
    answer = game_graph.load(g, game_graph.resolve(g, knowledge_id=13))
    assert answer["object"]["knowledge_id"] == 13
    assert answer["object"]["working"] == "*Proof.* w13"
    assert (answer["object"]["position"], answer["object"]["book_count"]) == (4, 22)
    members = {m["knowledge_id"]: m for m in answer["component"]}
    assert [m["knowledge_id"] for m in answer["component"]] == [12, 31, 14]
    assert (members[12]["why"], members[12]["of"]) == ("supports", 13)
    assert (members[31]["why"], members[31]["of"]) == ("proof_of", 13)
    assert (members[14]["why"], members[14]["of"]) == ("supports", 12)
    assert members[12]["working"] == "w12" and members[31]["working"] == "w31"
    assert members[12]["far"] is False
    assert members[31]["far"] is True
    assert members[31]["away"] == {"objects": 18, "direction": "later", "chapter": "3, Proofs"}
    assert answer["component_truncated"] is False
    deps = [(d["knowledge_id"], d["used_by"]) for d in answer["dependencies"]]
    assert deps == [(10, [12, 31]), (11, [13, 14])]
    assert "working" not in answer["dependencies"][0]


def test_load_from_a_detached_proof_finds_what_it_proves():
    g = graph()
    answer = game_graph.load(g, game_graph.resolve(g, knowledge_id=31))
    first = answer["component"][0]
    assert (first["knowledge_id"], first["why"], first["of"]) == (13, "proved_by", 31)
    assert {m["knowledge_id"] for m in answer["component"]} == {13, 12, 14}


def test_load_of_a_lone_object_has_an_empty_component():
    g = graph()
    answer = game_graph.load(g, game_graph.resolve(g, knowledge_id=10))
    assert answer["component"] == [] and answer["dependencies"] == []


def test_the_component_stops_at_its_limit():
    g = graph()
    for n in range(300, 340):
        g.obj(n, R, 111, "supporting_lemma", 9300 + n, order=100 + n)
        g.supports(n, 13)
    answer = game_graph.load(g, game_graph.resolve(g, knowledge_id=13))
    assert len(answer["component"]) == game_graph.COMPONENT_MEMBERS - 1
    assert answer["component_truncated"] is True


def test_resolve_by_source_key_refuses_hidden_and_ambiguous():
    g = graph()
    with pytest.raises(game_graph.NotFound):
        game_graph.resolve(g, knowledge_id=60)
    assert game_graph.resolve(g, source_key="k50")["knowledge_id"] == 50
    g.objects_by_id[51]["source_key"] = "k11"
    with pytest.raises(game_graph.Ambiguous):
        game_graph.resolve(g, source_key="k11")
    assert game_graph.resolve(g, source_key="k11", grimoire_id=M)["knowledge_id"] == 51


def test_crystal_lists_every_visible_book_preferred_first():
    g = graph()
    answer = game_graph.crystal(g, 9013)
    assert [(m["knowledge_id"], m["default"]) for m in answer["members"]] == [(50, True), (13, False)]
    assert answer["crystal_size"] == 2 and answer["truncated"] is False
    assert all(m["crystal_size"] == 2 for m in answer["members"])
    with pytest.raises(game_graph.NotFound):
        game_graph.crystal(g, 999)


def test_uses_and_used_by_in_book_order_with_crystals():
    g = graph()
    obj = game_graph.resolve(g, knowledge_id=12)
    uses = game_graph.arrows(g, obj, "uses")
    assert [r["knowledge_id"] for r in uses["results"]] == [10]
    used_by = game_graph.arrows(g, obj, "used_by")
    assert [r["knowledge_id"] for r in used_by["results"]] == [13, 31]
    assert used_by["results"][0]["crystal_id"] == 9013 and used_by["results"][0]["crystal_size"] == 2
    assert used_by["count"] == 2


def test_closure_walks_crystals_across_books_and_stops_at_references():
    g = graph()
    answer = game_graph.closure(g, game_graph.resolve(g, knowledge_id=52), reader_grimoire_id=R)
    by_crystal = {c["crystal_id"]: c for c in answer["crystals"]}
    assert [c["crystal_id"] for c in answer["crystals"]] == [9052, 9053, 9054, 9011, 9010]
    assert [c["depth"] for c in answer["crystals"]] == [0, 1, 1, 2, 3]
    start = by_crystal[9052]
    assert start["followed"] == [52] and start["next"] == [9053, 9054] and start["reader_members"] == []
    reference = by_crystal[9054]
    assert reference["walked"] is False and reference["reader_reference"] is True
    assert reference["reader_members"] == [40] and reference["shown"]["knowledge_id"] == 40
    connected = by_crystal[9011]
    assert connected["followed"] == [11] and connected["shown"]["knowledge_id"] == 11
    assert connected["reader_members"] == [11] and connected["transfers"] == 0
    assert by_crystal[9010]["transfers"] == 1
    assert answer["counted"] == [] and answer["gave_up"] is None
    assert answer["reader_grimoire_id"] == R and answer["start_crystal_id"] == 9052


def test_closure_up_follows_what_uses_it():
    g = graph()
    answer = game_graph.closure(g, game_graph.resolve(g, knowledge_id=10), direction="up")
    crystals = [c["crystal_id"] for c in answer["crystals"]]
    assert crystals[0] == 9010
    assert set(crystals) == {9010, 9011, 9012, 9013, 9014, 9031}


def test_closure_counts_past_the_budget_and_gives_up_past_ten_times():
    g = graph()
    obj = game_graph.resolve(g, knowledge_id=52)
    answer = game_graph.closure(g, obj, reader_grimoire_id=R, budget=10)
    assert [c["crystal_id"] for c in answer["crystals"]] == [9052]
    assert answer["words"]["shown"] == game_graph.words("Lemma 23.2") + game_graph.words(
        "A connected subspace lies in one side")
    assert sum(c["crystals"] for c in answer["counted"]) == 4
    # 9 words at depth 0 stay inside ten times a budget of 1; depth 1 passes it, so its crystals are not walked
    small = game_graph.closure(g, obj, reader_grimoire_id=R, budget=1)
    assert small["gave_up"]["depth"] == 1 and "10 words" in small["gave_up"]["reason"]
    assert small["crystals"][0]["walked"] is True
    assert small["counted"] == [{"depth": 1, "crystals": 2, "words": 6 + 4}]
    assert small["words"]["walked"] == 9 + 6 + 4


def test_words_count_a_formula_as_one():
    assert game_graph.words("If $f:X\\to Y$ is continuous") == 4


def test_section_in_book_order_with_its_place():
    g = graph()
    answer = game_graph.section(g, 111)
    assert [s["section_id"] for s in answer["path"]] == [110, 111]
    assert answer["previous"]["section_id"] == 110 and answer["next"]["section_id"] == 120
    assert answer["objects"][0]["knowledge_id"] == 11 and answer["objects"][0]["position"] == 2
    assert answer["section"]["book_title"] == "Topological Spaces"
    assert game_graph.section(g, 110)["children"] == [{"section_id": 111, "number": "1", "name": "Connected spaces"}]
    with pytest.raises(game_graph.NotFound):
        game_graph.section(g, 400)


def test_around_crosses_sections():
    g = graph()
    answer = game_graph.around(g, game_graph.resolve(g, knowledge_id=11), 2, 2)
    assert [o["knowledge_id"] for o in answer["before"]] == [10]
    assert [(o["knowledge_id"], o["position"]) for o in answer["after"]] == [(12, 3), (13, 4)]
    assert answer["object"]["position"] == 2 and answer["book_count"] == 22


def test_pages_give_storage_urls_and_page_numbers():
    g = graph()
    g.scans[13] = ([{"source_image_id": "p2", "storage_key": "books/18/pages/p 2.png", "url": "x",
                     "metadata": {"page": 2, "printed_page": "ii"}},
                    {"source_image_id": "p3", "storage_key": None, "url": "/old", "metadata": None}], [2, 3, "x"])
    answer = game_graph.pages(g, game_graph.resolve(g, knowledge_id=13))
    assert answer["pages"][0] == {"image": "p2", "url": "/api/v1/storage/books/18/pages/p%202.png",
                                  "page": 2, "printed_page": "ii"}
    assert answer["pages"][1] == {"image": "p3", "url": "/old", "page": None, "printed_page": None}
    assert answer["source_pages"] == [2, 3]


def test_match_names_one_object_or_none():
    g = graph()
    g.objects_by_id[51]["source_key"] = "k11"
    answer = game_graph.match(g, [{"source_key": "k13"}, {"source_key": "k11"},
                                  {"source_key": "k11", "grimoire_id": M}, {"source_key": "k60"},
                                  {"source_key": "nothing"}])
    assert [item["knowledge_id"] for item in answer["objects"]] == [13, None, 51, None, None]


# --- the SQL ---------------------------------------------------------------------------------

class RecordingCursor:
    def __init__(self, rows=None):
        self.statements = []
        self.rows = rows or []

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), params))

    def fetchall(self):
        return self.rows


DEMO = "source_metadata->>'demo' = 'true'"


@pytest.mark.parametrize("call", [
    lambda s: s.find(knowledge_id=1),
    lambda s: s.find(source_key="k", grimoire_id=2),
    lambda s: s.objects([1], working=True),
    lambda s: s.arrows([(18, 1)], "dependency", "in"),
    lambda s: s.arrows([(18, 1)], "supports", "out"),
    lambda s: s.positions(18, [1]),
    lambda s: s.window(18, 1, 5),
    lambda s: s.section_objects(18, 3, 10),
    lambda s: s.sections(18),
    lambda s: s.section(3),
    lambda s: s.members([9]),
    lambda s: s.pages(1),
    lambda s: s.match(["k"]),
])
def test_every_query_keeps_to_visible_books(call):
    cur = RecordingCursor()
    call(SqlGraph(cur))
    assert cur.statements and DEMO in cur.statements[0][0]


def test_queries_bind_their_values():
    cur = RecordingCursor()
    source = SqlGraph(cur)
    source.arrows([(18, 1), (18, 2)], "dependency", "out")
    sql, params = cur.statements[0]
    assert "e.source_knowledge_id = t.knowledge_id" in sql and "e.target_knowledge_id AS other" in sql
    assert params == ([18, 18], [1, 2], "dependency")
    source.find(source_key="scope-1:2", grimoire_id=25)
    sql, params = cur.statements[1]
    assert "k.source_key = %s AND s.grimoire_id = %s" in sql and params == ("scope-1:2", 25)
    assert source.objects([]) == {} and source.arrows([], "dependency", "in") == [] and source.members([]) == []
    assert len(cur.statements) == 2


def test_positions_read_the_count():
    cur = RecordingCursor([{"knowledge_id": 5, "position": 7, "total": 90}])
    assert SqlGraph(cur).positions(18, [5]) == ({5: 7}, 90)


# --- the routes -------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    g = graph()
    keys = []

    def key(request, *, kind, access_point=None, cost=1):
        keys.append((kind, access_point, cost))
        if request.headers.get("x-api-key") == "no-demo":
            raise game.GameError(403, "demo_access_required", "This account has no Web Demo access")
        return {"api_key_id": 1, "user_id": 7}

    @contextmanager
    def transaction():
        yield None, None

    monkeypatch.setattr(graph_router, "_key", key)
    monkeypatch.setattr(graph_router, "transaction", transaction)
    monkeypatch.setattr(graph_router, "SqlGraph", lambda cur: g)
    app = FastAPI()
    app.include_router(graph_router.router)
    game.install_error_handlers(app)
    test_client = TestClient(app)
    test_client.keys = keys
    test_client.graph = g
    return test_client


HEADERS = {"X-API-Key": "umst_read_test-key", "X-Install-Id": "k7m2qx"}


@pytest.mark.parametrize("path", [
    "/api/game/graph/object?knowledge_id=13",
    "/api/game/graph/object?source_key=k13",
    "/api/game/graph/crystal?knowledge_id=13",
    "/api/game/graph/crystal?crystal_id=9013",
    "/api/game/graph/uses?knowledge_id=13",
    "/api/game/graph/used-by?knowledge_id=13",
    "/api/game/graph/closure?knowledge_id=52&reader_grimoire_id=18&direction=down&words=3000",
    "/api/game/graph/closure?knowledge_id=10&direction=up",
    "/api/game/graph/section?section_id=111",
    "/api/game/graph/section?knowledge_id=13",
    "/api/game/graph/around?knowledge_id=13&before=2&after=2",
    "/api/game/graph/pages?knowledge_id=13",
])
def test_each_route_answers_once(client, path):
    response = client.get(path, headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert client.keys == [("graph", "demo", 1)]


def test_match_route(client):
    response = client.post("/api/game/graph/match", headers=HEADERS,
                           json={"objects": [{"source_key": "k13"}, {"source_key": "k50", "grimoire_id": 25}]})
    assert response.status_code == 200
    assert [o["knowledge_id"] for o in response.json()["objects"]] == [13, 50]
    too_many = client.post("/api/game/graph/match", headers=HEADERS,
                           json={"objects": [{"source_key": "k"}] * (game_graph.MATCH_MOST + 1)})
    assert too_many.status_code == 422 and too_many.json()["code"] == "invalid_request"


def test_route_refusals(client):
    both = client.get("/api/game/graph/object?knowledge_id=13&source_key=k13", headers=HEADERS)
    assert both.status_code == 422 and both.json()["code"] == "invalid_request"
    assert both.json()["errors"][0]["field"] == "knowledge_id"
    neither = client.get("/api/game/graph/uses", headers=HEADERS)
    assert neither.status_code == 422
    hidden = client.get("/api/game/graph/object?knowledge_id=60", headers=HEADERS)
    assert hidden.status_code == 404 and hidden.json()["code"] == "not_found"
    assert hidden.headers["cache-control"] == "no-store"
    assert client.get("/api/game/graph/section?section_id=400", headers=HEADERS).json()["code"] == "not_found"
    assert client.get("/api/game/graph/crystal?crystal_id=1", headers=HEADERS).status_code == 404
    client.graph.objects_by_id[51]["source_key"] = "k11"
    ambiguous = client.get("/api/game/graph/object?source_key=k11", headers=HEADERS)
    assert ambiguous.status_code == 409 and ambiguous.json()["code"] == "ambiguous"
    assert client.get("/api/game/graph/object?source_key=k11&grimoire_id=25", headers=HEADERS).status_code == 200
    budget = client.get("/api/game/graph/closure?knowledge_id=13&words=99", headers=HEADERS)
    assert budget.status_code == 422
    sideways = client.get("/api/game/graph/closure?knowledge_id=13&direction=sideways", headers=HEADERS)
    assert sideways.status_code == 422
    wide = client.get("/api/game/graph/around?knowledge_id=13&before=26", headers=HEADERS)
    assert wide.status_code == 422
    install = client.get("/api/game/graph/object?knowledge_id=13", headers={**HEADERS, "X-Install-Id": "bad id"})
    assert install.status_code == 422
    no_demo = client.get("/api/game/graph/object?knowledge_id=13", headers={"X-API-Key": "no-demo"})
    assert no_demo.status_code == 403 and no_demo.json()["code"] == "demo_access_required"


def test_the_key_is_checked_before_any_read(client):
    response = client.get("/api/game/graph/object?knowledge_id=13", headers={"X-API-Key": "no-demo"})
    assert response.status_code == 403
    assert client.graph.calls == []


# --- 0.0.20: answers that fit, and pages (C33) ------------------------------------------------

LONG = ("Let $X$ be a topological space and $f\\colon X\\to Y$ a continuous map onto a Hausdorff space $Y$; "
        "if every open cover of $X$ has a finite subcover, then the image $f(X)$ is compact and closed in $Y$, "
        "and $f$ is a closed map whenever $X$ is compact.")


def wide(users=300, members=0):
    """graph() with `users` objects of book 18 that each use 10, each its own crystal with a long statement, and
    `members` more members of 11's crystal in book 25."""
    g = graph()
    for n in range(users):
        g.obj(1000 + n, R, 111, "theorem", 20000 + n, name=f"Consequence {n}", label=f"Theorem 9.{n}",
              statement=LONG, order=5000 + n)
        g.uses(1000 + n, 10)
    for n in range(members):
        g.obj(5000 + n, M, 200, "definition", 9011, name=f"Connected, copy {n}", statement=LONG, order=10 + n)
    return g


def door_size(answer):
    """What the door hands an agent: json.dumps(answer, ensure_ascii=False)."""
    return len(json.dumps(answer, ensure_ascii=False))


def all_pages(read):
    """Every page of a paged read, from page 1 until `more` is false."""
    pages = [read(1)]
    while pages[-1]["more"]:
        pages.append(read(len(pages) + 1))
    return pages


def test_an_up_closure_at_5000_words_stays_under_its_character_cap():
    g = wide()
    obj = game_graph.resolve(g, knowledge_id=10)
    whole = game_graph.closure(g, obj, direction="up", budget=5000)
    assert door_size(whole) > 70000  # 0.0.19's answer, as in his run: too big for an agent
    pages = all_pages(lambda page: game_graph.closure(g, obj, direction="up", budget=5000, max_chars=30000,
                                                      page=page))
    assert len(pages) > 2 and all(door_size(answer) <= 30000 for answer in pages)
    assert [answer["page"] for answer in pages] == list(range(1, len(pages) + 1))
    ids = [c["crystal_id"] for answer in pages for c in answer["crystals"]]
    assert len(ids) == len(set(ids)) == 6 + 300
    assert ids[:len(whole["crystals"])] != [] and ids[0] == 9010


def test_closure_pages_cover_every_crystal_once_nearest_first():
    g = wide(users=120)
    obj = game_graph.resolve(g, knowledge_id=10)
    pages = all_pages(lambda page: game_graph.closure(g, obj, direction="up", budget=5000, max_chars=20000,
                                                      page=page))
    first = pages[0]
    ids = [c["crystal_id"] for answer in pages for c in answer["crystals"]]
    assert len(ids) == len(set(ids))
    assert set(ids) == {9010, 9011, 9012, 9013, 9014, 9031} | {20000 + n for n in range(120)}
    depths = [c["depth"] for answer in pages for c in answer["crystals"]]
    assert depths == sorted(depths)
    assert all(door_size(answer) <= 20000 for answer in pages)
    # `counted` counts what comes after the page, so the last page counts nothing
    assert pages[-1]["counted"] == []
    assert sum(c["crystals"] for c in first["counted"]) == len(ids) - len(first["crystals"])
    # compact: a book's title once under `books`, not in every shown object; the object asked about only named
    assert "book_title" not in first["crystals"][0]["shown"] and first["books"][str(R)] == "Topological Spaces"
    assert first["object"] == {"knowledge_id": 10, "source_key": "k10", "grimoire_id": R, "label": "Definition 1.1",
                               "name": "Topology", "type": "definition", "crystal_id": 9010}
    plain = game_graph.closure(g, obj, direction="up", budget=10000, page=1)
    assert plain["page"] == 1 and "books" not in plain and "book_title" in plain["crystals"][0]["shown"]


def test_closure_page_two_without_max_chars_shows_what_lies_past_the_budget():
    g = graph()
    obj = game_graph.resolve(g, knowledge_id=52)
    one = game_graph.closure(g, obj, reader_grimoire_id=R, budget=10)
    assert [c["crystal_id"] for c in one["crystals"]] == [9052]
    two = game_graph.closure(g, obj, reader_grimoire_id=R, budget=10, page=2)
    assert [c["crystal_id"] for c in two["crystals"]] == [9053, 9054]
    assert two["more"] is True and sum(c["crystals"] for c in two["counted"]) == 2
    past = game_graph.closure(g, obj, reader_grimoire_id=R, budget=10, page=9)
    assert past["crystals"] == [] and past["more"] is False


def test_a_crystal_with_many_members_comes_in_pages_with_the_readers_book_first():
    g = wide(users=0, members=700)
    whole = game_graph.crystal(g, 9011)
    assert whole["truncated"] is True and len(whole["members"]) == 500  # 0.0.19
    assert door_size(whole) > 100000
    pages = all_pages(lambda page: game_graph.crystal(g, 9011, reader_grimoire_id=R, max_chars=25000, page=page))
    first = pages[0]
    assert first["members"][0]["knowledge_id"] == 11  # the reader's book first (no preferred member here)
    assert "book_title" not in first["members"][0] and "crystal_id" not in first["members"][0]
    assert set(first["books"]) <= {str(R), str(M)}
    assert len(pages) > 2 and all(door_size(answer) <= 25000 for answer in pages)
    ids = [m["knowledge_id"] for answer in pages for m in answer["members"]]
    assert len(ids) == len(set(ids)) == 702


def test_used_by_comes_in_pages_within_the_cap():
    g = wide(users=650)
    obj = game_graph.resolve(g, knowledge_id=10)
    assert game_graph.arrows(g, obj, "used_by")["truncated"] is True  # 0.0.19 stops at 500
    pages = all_pages(lambda page: game_graph.arrows(g, obj, "used_by", max_chars=15000, page=page))
    assert all(door_size(answer) <= 15000 for answer in pages)
    ids = [r["knowledge_id"] for answer in pages for r in answer["results"]]
    assert len(ids) == len(set(ids)) == 650 + 3  # 11, 12 and 31 use 10 too
    assert pages[0]["books"] == {str(R): "Topological Spaces"}


def test_an_object_too_big_alone_is_cut_and_says_so():
    g = graph()
    g.obj(70, R, 111, "theorem", 9070, name="Huge", statement="word " * 20000, order=70)
    g.uses(70, 10)
    obj = game_graph.resolve(g, knowledge_id=10)
    pages = all_pages(lambda page: game_graph.closure(g, obj, direction="up", budget=10000, max_chars=5000,
                                                      page=page))
    assert all(door_size(answer) <= 5000 for answer in pages)
    huge = [c for answer in pages for c in answer["crystals"] if c["crystal_id"] == 9070]
    assert huge[0]["cut"] == ["statement"] and huge[0]["shown"]["statement"].endswith("[cut]")
    with pytest.raises(game_graph.TooSmall):
        game_graph.closure(g, obj, direction="up", max_chars=100)


def test_routes_take_max_chars_and_page(client):
    client.graph.__dict__.update(wide().__dict__)
    path = "/api/game/graph/closure?knowledge_id=10&direction=up&words=5000"
    whole = client.get(path, headers=HEADERS).json()
    assert door_size(whole) > 70000 and "page" not in whole
    capped = client.get(path + "&max_chars=30000", headers=HEADERS)
    assert capped.status_code == 200 and door_size(capped.json()) <= 30000 and capped.json()["more"] is True
    second = client.get(path + "&max_chars=30000&page=2", headers=HEADERS).json()
    assert second["page"] == 2 and door_size(second) <= 30000
    assert not {c["crystal_id"] for c in second["crystals"]} & {c["crystal_id"] for c in capped.json()["crystals"]}
    for route in ("crystal?crystal_id=9011", "uses?knowledge_id=13", "used-by?knowledge_id=10"):
        answer = client.get(f"/api/game/graph/{route}&max_chars=3000&page=1", headers=HEADERS)
        assert answer.status_code == 200 and door_size(answer.json()) <= 3000 and answer.json()["page"] == 1
    small = client.get(path + "&max_chars=1999", headers=HEADERS)
    assert small.status_code == 422 and small.json()["errors"][0]["field"].endswith("max_chars")
    assert client.get(path + "&page=0", headers=HEADERS).status_code == 422


# --- 0.0.20: one closure from several objects, cancelled branches left out (C57) ---------------

def crystals_of(answer):
    return [c["crystal_id"] for c in answer["crystals"]]


def test_one_closure_from_two_objects_with_one_crystal_left_out():
    g = graph()
    starts = [game_graph.resolve(g, knowledge_id=13), game_graph.resolve(g, knowledge_id=52)]
    both = game_graph.closure(g, starts[0], starts=starts, reader_grimoire_id=R)
    # one walk: both starts at depth 0, the crystal they share (9011, "Connected") found once
    assert crystals_of(both) == [9013, 9052, 9011, 9012, 9053, 9054, 9010]
    assert [c["depth"] for c in both["crystals"]] == [0, 0, 1, 1, 1, 1, 2]
    assert both["start_crystal_ids"] == [9013, 9052]
    assert [o["knowledge_id"] for o in both["objects"]] == [13, 52] and "object" not in both
    # cancel 9011: it is not entered, and 9010 stays because 9012 (kept) still leads to it
    no_connected = game_graph.closure(g, starts[0], starts=starts, reader_grimoire_id=R, leave_out=[9011])
    assert crystals_of(no_connected) == [9013, 9052, 9012, 9053, 9054, 9010]
    assert 9011 not in no_connected["crystals"][0]["next"] and no_connected["left_out"] == [9011]
    # cancel 9011 and 9012: nothing kept leads to 9010 any more, so it goes too
    neither = game_graph.closure(g, starts[0], starts=starts, reader_grimoire_id=R, leave_out=[9011, 9012])
    assert crystals_of(neither) == [9013, 9052, 9053, 9054]
    # a start's own crystal is never left out
    kept = game_graph.closure(g, starts[0], starts=starts, reader_grimoire_id=R, leave_out=[9052])
    assert crystals_of(kept) == crystals_of(both) and kept["left_out"] == []


def test_the_shared_closure_is_not_the_two_closures_glued():
    g = graph()
    a = game_graph.closure(g, game_graph.resolve(g, knowledge_id=13), reader_grimoire_id=R)
    b = game_graph.closure(g, game_graph.resolve(g, knowledge_id=52), reader_grimoire_id=R)
    starts = [game_graph.resolve(g, knowledge_id=13), game_graph.resolve(g, knowledge_id=52)]
    both = game_graph.closure(g, starts[0], starts=starts, reader_grimoire_id=R)
    glued = crystals_of(a) + crystals_of(b)
    assert len(glued) > len(set(glued))  # asked one by one, the shared crystals come twice
    assert sorted(crystals_of(both)) == sorted(set(glued))
    assert both["words"]["walked"] < a["words"]["walked"] + b["words"]["walked"]


def test_the_closure_route_takes_objects_and_leave_out(client):
    base = "/api/game/graph/closure?reader_grimoire_id=18"
    commas = client.get(base + "&objects=13,52&leave_out=9011", headers=HEADERS)
    assert commas.status_code == 200, commas.text
    assert crystals_of(commas.json()) == [9013, 9052, 9012, 9053, 9054, 9010]
    repeated = client.get(base + "&objects=13&objects=52&leave_out=9011&leave_out=9012", headers=HEADERS)
    assert crystals_of(repeated.json()) == [9013, 9052, 9053, 9054] and repeated.json()["left_out"] == [9011, 9012]
    assert client.keys == [("graph", "demo", 1)] * 2
    one = client.get(base + "&knowledge_id=13&leave_out=9012", headers=HEADERS).json()
    assert one["object"]["knowledge_id"] == 13 and 9012 not in crystals_of(one)
    missing = client.get(base + "&objects=13,60,99", headers=HEADERS)
    assert missing.status_code == 404 and missing.json()["detail"].endswith(": 60, 99")
    both = client.get(base + "&objects=13&knowledge_id=13", headers=HEADERS)
    assert both.status_code == 422 and both.json()["errors"][0]["field"] == "objects"
    bad = client.get(base + "&objects=13,x", headers=HEADERS)
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "objects"
    many = client.get(base + "&objects=" + ",".join(str(n) for n in range(1, 102)), headers=HEADERS)
    assert many.status_code == 422
    capped = client.get(base + "&objects=13,52&max_chars=2500", headers=HEADERS)
    assert capped.status_code == 200 and door_size(capped.json()) <= 2500


# --- 0.0.20: the whole support component, the cut being the size only (C60) ----------------------

def supported(lemmas=40, working="w"):
    """graph() with `lemmas` more supporting lemmas of 13, each with a working."""
    g = graph()
    for n in range(lemmas):
        g.obj(300 + n, R, 111, "supporting_lemma", 9300 + n, name=f"Step {n}", statement=LONG, working=working,
              order=100 + n)
        g.supports(300 + n, 13)
    return g


def test_the_load_gives_the_whole_component_past_24_members():
    g = supported(40, working=LONG * 3)
    obj = game_graph.resolve(g, knowledge_id=13)
    old = game_graph.load(g, obj)
    assert len(old["component"]) == 23 and old["component_truncated"] is True  # 0.0.19, as the tutor's MEMBERS
    pages = all_pages(lambda page: game_graph.load(g, obj, max_chars=40000, page=page))
    assert all(door_size(answer) <= 40000 for answer in pages) and len(pages) > 1
    members = [m["knowledge_id"] for answer in pages for m in answer["component"]]
    assert len(members) == len(set(members)) == 43 == pages[0]["component_size"]
    assert set(members) == {12, 31, 14} | {300 + n for n in range(40)}
    assert pages[0]["component_truncated"] is False
    dependencies = [d["knowledge_id"] for answer in pages for d in answer["dependencies"]]
    assert dependencies == [10, 11] and pages[0]["dependencies_size"] == 2
    # each page says how much is still to come
    first = pages[0]
    assert first["later"]["component"] == 43 - len(first["component"])
    assert pages[-1]["later"] == {"component": 0, "dependencies": 0}
    assert first["object"]["working"] == "*Proof.* w13" and "book_title" not in first["object"]
    assert pages[1]["object"]["knowledge_id"] == 13 and "working" not in pages[1]["object"]


def test_a_long_working_is_cut_and_the_load_says_so():
    g = supported(2, working="step " * 30000)
    obj = game_graph.resolve(g, knowledge_id=13)
    pages = all_pages(lambda page: game_graph.load(g, obj, max_chars=20000, page=page))
    assert all(door_size(answer) <= 20000 for answer in pages)
    cut = [m for answer in pages for m in answer["component"] if m.get("cut")]
    assert {m["knowledge_id"] for m in cut} == {300, 301}
    assert all(m["cut"] == ["working"] and m["working"].endswith("[cut]") for m in cut)


def test_a_crystal_member_too_big_alone_is_cut():
    g = graph()
    g.obj(71, M, 200, "definition", 9011, name="Wordy", statement="word " * 20000, order=71)
    pages = all_pages(lambda page: game_graph.crystal(g, 9011, max_chars=4000, page=page))
    assert all(door_size(answer) <= 4000 for answer in pages)
    wordy = [m for answer in pages for m in answer["members"] if m["knowledge_id"] == 71]
    assert wordy[0]["cut"] == ["statement"] and wordy[0]["statement"].endswith("[cut]")


def test_the_object_route_takes_max_chars_and_page(client):
    client.graph.__dict__.update(supported(40).__dict__)
    old = client.get("/api/game/graph/object?knowledge_id=13", headers=HEADERS).json()
    assert len(old["component"]) == 23 and "component_size" not in old
    first = client.get("/api/game/graph/object?knowledge_id=13&max_chars=40000", headers=HEADERS)
    assert first.status_code == 200 and first.json()["component_size"] == 43
    assert door_size(first.json()) <= 40000
    whole = client.get("/api/game/graph/object?knowledge_id=13&page=1", headers=HEADERS).json()
    assert len(whole["component"]) == 43 and whole["more"] is False
