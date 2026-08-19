from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import dependencies
from app.services import corpus_access


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (ROOT / "backend/sql/007_research_corpus_access.sql").read_text(encoding="utf-8")
SCHEMA = (ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8")
DEMO_SOURCE = (ROOT / "backend/python/app/routers/demo.py").read_text(encoding="utf-8")
ADMIN_SOURCE = (ROOT / "backend/python/app/routers/admin.py").read_text(encoding="utf-8")
CONTENT_SOURCE = (ROOT / "backend/python/app/routers/content.py").read_text(encoding="utf-8")
MAIN_SOURCE = (ROOT / "backend/python/app/main.py").read_text(encoding="utf-8")

SYNTHETIC_ALLOWED_A = 910_001
SYNTHETIC_ALLOWED_B = 910_002
SYNTHETIC_DENIED = 910_099


class Cursor:
    def __init__(self, *, one=(), all_rows=()):
        self.one = list(one)
        self.all_rows = list(all_rows)
        self.queries = []

    def execute(self, query, values=None):
        self.queries.append((query, values))

    def fetchone(self):
        return self.one.pop(0)

    def fetchall(self):
        return self.all_rows.pop(0)


@pytest.mark.parametrize("role", ["user", "staff", "admin", "superadmin"])
def test_role_never_grants_protected_corpus_access(role):
    actor = {"user_id": SYNTHETIC_DENIED, "authority_type": role}
    assert corpus_access.actor_user_id(actor) == SYNTHETIC_DENIED
    assert corpus_access.pure_access_decision(
        protected=True,
        user_id=corpus_access.actor_user_id(actor),
        active_user_ids=(SYNTHETIC_ALLOWED_A, SYNTHETIC_ALLOWED_B),
    ) is False


@pytest.mark.parametrize("allowed", [SYNTHETIC_ALLOWED_A, SYNTHETIC_ALLOWED_B])
def test_exact_synthetic_allowlisted_users_are_allowed(allowed):
    assert corpus_access.pure_access_decision(
        protected=True,
        user_id=allowed,
        active_user_ids=(SYNTHETIC_ALLOWED_A, SYNTHETIC_ALLOWED_B),
    ) is True
    assert corpus_access.pure_access_decision(
        protected=True,
        user_id=None,
        active_user_ids=(SYNTHETIC_ALLOWED_A, SYNTHETIC_ALLOWED_B),
    ) is False


def test_unprotected_visibility_is_separate_from_research_authorization():
    assert corpus_access.pure_access_decision(
        protected=False,
        user_id=None,
        active_user_ids=(),
    ) is True


@pytest.mark.parametrize("configured", [None, "", "off", "db", "database-mode"])
def test_absent_or_malformed_policy_fails_closed(monkeypatch, configured, caplog):
    if configured is None:
        monkeypatch.delenv(corpus_access.POLICY_MODE_ENV, raising=False)
    else:
        monkeypatch.setenv(corpus_access.POLICY_MODE_ENV, configured)
    assert corpus_access.ensure_policy_ready(
        user_id=SYNTHETIC_DENIED,
        surface="demo_book",
        list_request=True,
    ) is False
    with pytest.raises(HTTPException) as caught:
        corpus_access.ensure_policy_ready(
            user_id=SYNTHETIC_DENIED,
            surface="demo_book",
        )
    assert caught.value.status_code == 404
    assert caught.value.detail == "Resource not found"
    assert caught.value.headers == {
        corpus_access.ACCESS_REVISION_HEADER: "v1.unavailable"
    }
    assert str(SYNTHETIC_DENIED) not in caplog.text


def test_audit_event_is_pseudonymous_and_data_minimal(monkeypatch, caplog):
    monkeypatch.setenv(corpus_access.AUDIT_KEY_ENV, "x" * 40)
    caplog.set_level("WARNING", logger="theumst.security.corpus_access")
    corpus_access.audit_denied_access(
        user_id=SYNTHETIC_DENIED,
        surface="demo_search",
        reason="not_allowlisted",
    )
    event = caplog.text
    assert "protected_corpus_access_denied" in event
    assert "actor=pseudonymous:" in event
    assert str(SYNTHETIC_DENIED) not in event
    for forbidden in (
        "learner@example.test",
        "a mathematical passage",
        "https://objects.example.test/signed",
        "vector",
        "grimoire_id",
    ):
        assert forbidden not in event


def test_audit_without_protected_key_never_uses_unsalted_identifier(monkeypatch, caplog):
    monkeypatch.delenv(corpus_access.AUDIT_KEY_ENV, raising=False)
    caplog.set_level("WARNING", logger="theumst.security.corpus_access")
    corpus_access.audit_denied_access(
        user_id=SYNTHETIC_DENIED,
        surface="asset",
        reason="not_allowlisted",
    )
    assert "actor=authenticated" in caplog.text
    assert str(SYNTHETIC_DENIED) not in caplog.text


def _revision_rows(access_revision: int, *, active: bool):
    return [[{
        "grimoire_id": 700_001,
        "policy_revision": 800_001,
        "access_revision": access_revision,
        "active": active,
    }]]


def test_revision_changes_across_active_revoke_regrant_and_never_regresses(monkeypatch):
    monkeypatch.setenv(corpus_access.POLICY_MODE_ENV, "database")
    monkeypatch.setenv(corpus_access.AUDIT_KEY_ENV, "revision-test-key-which-is-at-least-32-bytes")
    active_v1 = corpus_access.access_revision_token(
        Cursor(all_rows=_revision_rows(900_001, active=True)),
        SYNTHETIC_ALLOWED_A,
    )
    revoked_v2 = corpus_access.access_revision_token(
        Cursor(all_rows=_revision_rows(900_002, active=False)),
        SYNTHETIC_ALLOWED_A,
    )
    regranted_v3 = corpus_access.access_revision_token(
        Cursor(all_rows=_revision_rows(900_003, active=True)),
        SYNTHETIC_ALLOWED_A,
    )
    assert len({active_v1, revoked_v2, regranted_v3}) == 3
    assert all(value.startswith("v1.") for value in (active_v1, revoked_v2, regranted_v3))


def test_revision_is_deterministic_for_concurrent_bootstrap(monkeypatch):
    monkeypatch.setenv(corpus_access.POLICY_MODE_ENV, "database")
    monkeypatch.setenv(corpus_access.AUDIT_KEY_ENV, "revision-test-key-which-is-at-least-32-bytes")
    first = corpus_access.access_revision_token(
        Cursor(all_rows=_revision_rows(900_010, active=True)),
        SYNTHETIC_ALLOWED_A,
    )
    second = corpus_access.access_revision_token(
        Cursor(all_rows=_revision_rows(900_010, active=True)),
        SYNTHETIC_ALLOWED_A,
    )
    assert first == second


@pytest.mark.parametrize("surface", ["asset", "demo_graph", "demo_search", "demo_note"])
def test_inflight_protected_response_token_mismatches_new_bootstrap(monkeypatch, surface):
    monkeypatch.setenv(corpus_access.POLICY_MODE_ENV, "database")
    monkeypatch.setenv(corpus_access.AUDIT_KEY_ENV, "revision-test-key-which-is-at-least-32-bytes")
    old_response = corpus_access.revision_headers(
        Cursor(all_rows=_revision_rows(900_020, active=True)),
        SYNTHETIC_ALLOWED_A,
    )
    new_bootstrap = corpus_access.revision_headers(
        Cursor(all_rows=_revision_rows(900_021, active=False)),
        SYNTHETIC_ALLOWED_A,
    )
    assert surface
    assert old_response[corpus_access.ACCESS_REVISION_HEADER] != new_bootstrap[corpus_access.ACCESS_REVISION_HEADER]
    assert old_response["Cache-Control"] == "private, no-store"
    assert old_response["Vary"] == "Authorization, Cookie, Accept-Encoding"


def _hidden_miss(monkeypatch, protected: bool):
    monkeypatch.setenv(corpus_access.POLICY_MODE_ENV, "database")
    monkeypatch.setenv(corpus_access.AUDIT_KEY_ENV, "revision-test-key-which-is-at-least-32-bytes")
    cursor = Cursor(
        one=[{"protected": protected}],
        all_rows=_revision_rows(900_030, active=False),
    )
    with pytest.raises(HTTPException) as caught:
        corpus_access.raise_hidden_knowledge_miss(
            cursor,
            knowledge_id=700_099,
            user_id=SYNTHETIC_DENIED,
            surface="demo_knowledge",
        )
    return caught.value


def test_protected_and_nonexistent_direct_404_are_identical(monkeypatch):
    protected = _hidden_miss(monkeypatch, True)
    nonexistent = _hidden_miss(monkeypatch, False)
    assert protected.status_code == nonexistent.status_code == 404
    assert protected.detail == nonexistent.detail == "Resource not found"
    assert protected.headers == nonexistent.headers
    assert protected.headers["Cache-Control"] == "private, no-store"
    assert protected.headers["Vary"] == "Authorization, Cookie, Accept-Encoding"


def test_visibility_sql_uses_only_stable_user_id_allowlist():
    sql = corpus_access.corpus_visibility_sql("s.grimoire_id")
    assert "research_corpus_policy" in sql
    assert "research_corpus_user_access" in sql
    assert "rcua.user_id = %s" in sql
    for forbidden in ("authority", "role", "email", "username", "title"):
        assert forbidden not in sql.lower()


def test_demo_visibility_separates_public_flag_from_research_allowlist():
    sql = corpus_access.demo_corpus_visibility_sql("g.grimoire_id")
    assert "source_metadata->>'demo'" in sql
    assert "NOT EXISTS" in sql
    assert "research_corpus_policy" in sql
    assert "research_corpus_user_access" in sql
    assert "allowed.user_id = %s" in sql
    # Every demo corpus read uses the centralized rule: protected allowlisted
    # research access does not depend on demo=true, while unprotected access does.
    assert not re.search(r"(?<!demo_)corpus_visibility_sql\(", DEMO_SOURCE)
    assert "source_metadata->>'demo'" not in DEMO_SOURCE
    assert DEMO_SOURCE.count("demo_corpus_visibility_sql(") >= 16


def test_image_rows_never_return_stored_direct_url():
    rows = corpus_access.secure_image_rows([
        {
            "storage_key": "books/synthetic/images/diagram.png",
            "url": "https://objects.example.test/private-signature",
        },
        {"url": "https://objects.example.test/orphan"},
    ])
    assert rows == [{
        "storage_key": "books/synthetic/images/diagram.png",
        "url": "/api/v1/storage/books/synthetic/images/diagram.png",
    }]


def test_signed_asset_ttl_is_bounded(monkeypatch):
    monkeypatch.setenv(corpus_access.ASSET_TTL_ENV, "999999")
    assert corpus_access.signed_asset_ttl_seconds() == 900
    monkeypatch.setenv(corpus_access.ASSET_TTL_ENV, "1")
    assert corpus_access.signed_asset_ttl_seconds() == 60
    monkeypatch.setenv(corpus_access.ASSET_TTL_ENV, "malformed")
    assert corpus_access.signed_asset_ttl_seconds() == 300


def test_predeployment_gate_requires_exact_configured_active_count(monkeypatch):
    monkeypatch.setenv(corpus_access.POLICY_MODE_ENV, "database")
    not_ready = Cursor(one=[{"ready": False}])
    with pytest.raises(RuntimeError, match="Protected corpus policy is not ready"):
        corpus_access.assert_protected_corpus_policy_ready(not_ready)
    sql = not_ready.queries[0][0]
    assert "required_active_user_count" in sql
    assert "object_key_prefix" in sql
    ready = Cursor(one=[{"ready": True}])
    corpus_access.assert_protected_corpus_policy_ready(ready)


def test_schema_and_migration_use_nonrepeating_revision_sequences_and_no_real_ids():
    for sql in (SCHEMA, MIGRATION):
        assert "research_corpus_policy_revision_seq" in sql
        assert "research_corpus_access_revision_seq" in sql
        assert "nextval('research_corpus_access_revision_seq')" in sql
        assert "required_active_user_count" in sql
        assert "object_key_prefix" in sql
        assert "BEFORE INSERT OR UPDATE ON research_corpus_policy" in sql
        assert "BEFORE INSERT OR UPDATE ON research_corpus_user_access" in sql
    assert "INSERT INTO research_corpus_user_access" not in MIGRATION
    assert "INSERT INTO research_corpus_policy" not in MIGRATION


def test_media_link_and_protected_preservation_contract_is_additive():
    assert "ADD COLUMN IF NOT EXISTS grimoire_id" in MIGRATION
    assert "ON DELETE RESTRICT" in MIGRATION


def test_revision_is_captured_before_body_and_never_requeried_afterward():
    middleware = MAIN_SOURCE.split("async def protected_access_revision", 1)[1]
    before_body, after_body = middleware.split("response = await call_next(request)", 1)
    assert "current_user(request)" in before_body
    assert "revision_headers" in before_body
    assert "current_user(request)" not in after_body
    assert "with transaction()" not in after_body.split("return response", 1)[0]
    assert "request.state.protected_access_headers" in before_body


def test_current_user_revalidates_session_once_per_request(monkeypatch):
    calls = []

    class AuthCursor:
        def execute(self, query, values=None):
            calls.append((query, values))

        def fetchone(self):
            return {"user_id": SYNTHETIC_ALLOWED_A, "email_verified_at": "synthetic"}

    class AuthTransaction:
        def __enter__(self):
            return object(), AuthCursor()

        def __exit__(self, exc_type, exc, tb):
            return False

    request = SimpleNamespace(
        cookies={"synthetic_session": "synthetic-token"},
        state=SimpleNamespace(),
    )
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(cookie_name="synthetic_session"),
    )
    monkeypatch.setattr(dependencies, "hash_secret", lambda value: "synthetic-hash")
    monkeypatch.setattr(dependencies, "transaction", lambda: AuthTransaction())
    first = dependencies.current_user(request)
    second = dependencies.current_user(request)
    assert first is second
    assert first["user_id"] == SYNTHETIC_ALLOWED_A
    assert len(calls) == 1
    assert "s.revoked_at IS NULL" in calls[0][0]
    assert "u.email_verified_at IS NOT NULL" in calls[0][0]


def test_public_image_mount_cannot_overlap_private_book_storage(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    safe_storage = tmp_path / "private"
    settings = SimpleNamespace(
        server="LOCAL",
        local_storage_dir=str(safe_storage),
        public_images=public,
    )
    corpus_access.assert_public_image_mount_isolated(settings)
    settings.local_storage_dir = str(public / "books")
    with pytest.raises(RuntimeError, match="must be isolated"):
        corpus_access.assert_public_image_mount_isolated(settings)
    assert 'application.mount("/images", StaticFiles(directory=settings.public_images)' in MAIN_SOURCE
    assert 'request.url.path.startswith("/api/v1/storage/")' in MAIN_SOURCE


def test_storage_listing_authorizes_before_any_storage_io():
    function = ADMIN_SOURCE.split("def list_storage", 1)[1].split("@router.get", 1)[0]
    assert function.index("require_storage_key_access") < function.index("storage.list_items")
    assert function.index("storage.list_items") < function.index("filter_storage_items")


def test_protected_corpus_delete_is_deliberately_blocked():
    function = CONTENT_SOURCE.split("def delete_book", 1)[1].split("def _slug_base", 1)[0]
    assert "research_corpus_policy" in function
    assert "Protected research books cannot be deleted" in function
    assert function.index("research_corpus_policy") < function.index("DELETE FROM grimoire")
