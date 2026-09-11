"""Opt-in real PostgreSQL acceptance. Never uses a production DB or email transport.

Set THEUMST_NEWS_DB_TESTS=1 with a LOCAL loopback database account allowed to
create a temporary database. The fixture builds and removes only its UUID-named
database; the configured source database and its browser fixtures are untouched.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from fastapi.testclient import TestClient

from app import database
from app.config import get_settings
from app.main import create_app
from app.routers import auth
from app.security import hash_password, hash_secret
from app.services import news


pytestmark = pytest.mark.skipif(os.getenv("THEUMST_NEWS_DB_TESTS") != "1", reason="Explicit isolated PostgreSQL acceptance only")


@pytest.fixture(scope="module")
def isolated_database():
    from psycopg2 import sql
    settings = get_settings()
    assert settings.server == "LOCAL" and settings.db_host in {"127.0.0.1", "localhost"}
    assert not settings.news_delivery_enabled
    name = f"theumst_news_test_{uuid4().hex}"
    admin = database.connect()
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    def connect():
        return psycopg2.connect(dbname=name, user=settings.db_user, password=settings.db_password,
                                host=settings.db_host, port=settings.db_port, cursor_factory=RealDictCursor)
    patch = pytest.MonkeyPatch()
    patch.setattr(database, "connect", connect)
    try:
        with database.transaction() as (_, cur):
            cur.execute((settings.sql_dir / "schema.sql").read_text(encoding="utf-8"))
        yield
    finally:
        patch.undo()
        with admin.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


@pytest.fixture(autouse=True)
def clean_private_database(isolated_database, monkeypatch):
    with database.transaction() as (_, cur):
        cur.execute('TRUNCATE "user", media_post, news_provider_event, news_suppression, news_consent_event CASCADE')
    def forbidden_send(*args, **kwargs):
        raise AssertionError("A real provider send is forbidden in acceptance tests")
    monkeypatch.setattr(news, "send_resend", forbidden_send)


@pytest.fixture
def client():
    with TestClient(create_app(initialize_services=False)) as client:
        yield client


def account(*, confirmed=True, role="user", subscribed=False):
    label = f"news_{uuid4().hex[:16]}"
    email = f"{label}@example.invalid"
    with database.transaction() as (_, cur):
        cur.execute(
            '''INSERT INTO "user" (username, email, password_hash, authority_id, email_verified_at)
               SELECT %s, %s, %s, authority_id, %s FROM authority WHERE name = %s RETURNING user_id''',
            (label, email, hash_password("fixture-passphrase-123"), datetime.now(timezone.utc) if confirmed else None, role),
        )
        user_id = cur.fetchone()["user_id"]
        if subscribed:
            news.set_subscription(cur, user_id, True, "profile")
    return {"id": user_id, "username": label, "email": email, "password": "fixture-passphrase-123"}


def login(client, user, **extra):
    return client.post("/auth/login", data={"username": user["username"], "password": user["password"], **extra},
                       headers={"Accept": "application/json"})


def publish(client, **extra):
    payload = {"title": "A quiet update", "body": "The full story lives here.", "status": "published",
               "email_introduction": "A short invitation.", "announce": True, "request_id": str(uuid4()), **extra}
    response = client.post("/api/content/media", json=payload)
    assert response.status_code == 201, response.text
    return response.json(), payload


def rows(query, params=()):
    with database.transaction() as (_, cur):
        cur.execute(query, params)
        return list(cur.fetchall())


def test_pending_login_consent_preserves_authentication_and_explicit_choice(client):
    user = account(confirmed=False)
    wrong = {**user, "password": "incorrect"}
    assert login(client, wrong, news_opt_in="on").status_code == 401
    assert rows("SELECT 1 FROM news_subscription") == []
    response = login(client, user, news_opt_in="on")
    assert response.status_code == 403 and response.json()["code"] == "email_unverified"
    assert rows("SELECT 1 FROM web_session") == []
    with database.transaction() as (_, cur):
        state = news.subscription_state(cur, user["id"])
        assert state["status"] == "pending_confirmation" and state["consent_source"] == "login"
        token = auth._issue_email_verification(cur, user["id"], 24)
        cur.execute("UPDATE email_verification_token SET sent_at = now() WHERE user_id = %s", (user["id"],))
    assert client.post("/auth/email-verification/confirm", json={"token": token}).status_code == 200
    assert login(client, user).status_code == 200
    response = client.get("/api/me/subscriptions")
    assert response.json()["status"] == "active"
    assert len(rows("SELECT 1 FROM news_consent_event")) == 1
    # An unchecked login never cancels an existing subscription.
    assert login(client, user, news_opt_in="").status_code == 200
    assert client.get("/api/me/subscriptions").json()["news"] is True


def test_profile_api_owns_only_current_user_and_defaults_off(client):
    assert client.get("/api/me/subscriptions").status_code == 401
    user = account()
    other = account(subscribed=True)
    assert login(client, user).status_code == 200
    assert client.get("/api/me/subscriptions").json()["status"] == "off"
    assert client.put("/api/me/subscriptions", json={"news": True, "user_id": other["id"]}).json()["status"] == "active"
    assert client.put("/api/me/subscriptions", json={"news": False}).json()["status"] == "off"
    assert rows("SELECT enabled FROM news_subscription WHERE user_id = %s", (other["id"],))[0]["enabled"]
    assert client.post("/api/content/media/email-preview", json={"title": "News", "email_introduction": "Hello"}).status_code == 403


def test_publication_freezes_only_confirmed_audience_and_deduplicates_edits(client):
    account(subscribed=True)
    account(confirmed=False, subscribed=True)
    account(subscribed=False)
    editor = account(role="admin")
    assert login(client, editor).status_code == 200
    preview = client.post("/api/content/media/email-preview", json={"title": "A quiet update", "email_introduction": "A short invitation."})
    assert preview.status_code == 200 and 'href="' not in preview.json()["html"]
    assert "[preview]" in preview.json()["text"]
    assert rows("SELECT 1 FROM news_delivery") == []
    published, payload = publish(client)
    assert published["announcement_queued"] is True
    deliveries = rows("SELECT * FROM news_delivery")
    assert len(deliveries) == 1
    headers = deliveries[0]["payload"]["headers"]
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert headers["List-Unsubscribe"].startswith("<http")
    assert client.get(f"/api/news/{published['slug']}").status_code == 200
    edited = client.put(f"/api/content/media/{published['media_post_id']}", json={**payload, "title": "Edited title"})
    assert edited.status_code == 200
    assert edited.json()["slug"] == published["slug"]
    assert edited.json()["announcement_id"] == published["announcement_id"]
    assert edited.json()["announcement_queued"] is False
    assert rows("SELECT payload FROM news_delivery")[0]["payload"] == deliveries[0]["payload"]
    assert client.get("/api/content/media").json()["posts"][0]["announcement_queued_at"]
    assert client.put(f"/api/content/media/{published['media_post_id']}", json={**payload, "announce": False, "status": "draft"}).status_code == 409
    assert client.delete(f"/api/content/media/{published['media_post_id']}").status_code == 409
    draft, _ = publish(client, title="Private draft", status="draft", announce=False)
    assert client.get(f"/api/news/{draft['slug']}").status_code == 404


def test_unsubscribe_get_does_not_mutate_and_old_links_work_after_reoptin(client):
    user = account(subscribed=True)
    token = rows("SELECT unsubscribe_token FROM news_subscription")[0]["unsubscribe_token"]
    path = f"/api/news/unsubscribe/{token}"
    assert client.get(path).status_code == 200
    assert rows("SELECT enabled FROM news_subscription")[0]["enabled"] is True
    assert client.post(path, data={"List-Unsubscribe": "One-Click"}).status_code == 200
    assert rows("SELECT enabled FROM news_subscription")[0]["enabled"] is False
    assert client.post(path).status_code == 200
    assert len(rows("SELECT 1 FROM news_consent_event")) == 2
    with database.transaction() as (_, cur):
        news.set_subscription(cur, user["id"], True, "profile")
    assert client.post(path).status_code == 200
    assert rows("SELECT enabled FROM news_subscription")[0]["enabled"] is False


def test_email_change_confirmation_does_not_transfer_news_consent(client):
    user = account(subscribed=True)
    assert login(client, user).status_code == 200
    with database.transaction() as (_, cur):
        token = auth._issue_email_change(cur, user["id"], "new-fixture@example.invalid", 24)
        cur.execute("UPDATE email_change_token SET sent_at = now() WHERE user_id = %s", (user["id"],))
    assert client.post("/auth/email-change/confirm", json={"token": token}).status_code == 200
    assert client.get("/api/me/subscriptions").status_code == 401  # Existing session is still revoked.
    assert login(client, user).status_code == 200
    state = client.get("/api/me/subscriptions").json()
    assert state["status"] == "off" and state["email"] == "new-fixture@example.invalid"
    assert rows("SELECT email FROM news_subscription")[0]["email"] == user["email"]
    assert client.put("/api/me/subscriptions", json={"news": True}).json()["status"] == "active"
    assert rows("SELECT email FROM news_subscription")[0]["email"] == "new-fixture@example.invalid"


def test_worker_retries_identical_payload_then_stops_past_provider_window(client):
    account(subscribed=True)
    assert login(client, account(role="admin")).status_code == 200
    publish(client)
    calls = []
    def timeout(payload, delivery_id, **kwargs):
        calls.append((payload, delivery_id))
        raise httpx.ReadTimeout("test ambiguity")
    assert news.process_one(sender=timeout)
    delivery = rows("SELECT * FROM news_delivery")[0]
    assert delivery["status"] == "queued" and delivery["attempts"] == 1
    rows("UPDATE news_delivery SET next_attempt_at = now() RETURNING delivery_id")
    def accepted(payload, delivery_id, **kwargs):
        calls.append((payload, delivery_id))
        return "provider-same-attempt"
    assert news.process_one(sender=accepted)
    assert calls[0] == calls[1]
    assert rows("SELECT status FROM news_delivery")[0]["status"] == "sent"
    publish(client, title="Another announcement")
    news.process_one(sender=timeout)
    rows("UPDATE news_delivery SET first_attempt_at = now() - interval '24 hours', next_attempt_at = now() WHERE status = 'queued' RETURNING delivery_id")
    assert news.process_one(sender=accepted)
    assert len(calls) == 3
    assert len(rows("SELECT 1 FROM news_delivery WHERE status = 'uncertain'")) == 1


def test_worker_rechecks_consent_and_multiple_workers_claim_once(client):
    user = account(subscribed=True)
    assert login(client, account(role="admin")).status_code == 200
    publish(client)
    with database.transaction() as (_, cur):
        news.set_subscription(cur, user["id"], False, "profile")
        news.set_subscription(cur, user["id"], True, "profile")
    # Re-opt-in is new consent; it cannot revive an old campaign's queued send.
    assert news.process_one()
    assert rows("SELECT status FROM news_delivery")[0]["status"] == "skipped"
    publish(client, title="Fresh consent")
    calls = []
    def accepted(payload, delivery_id, **kwargs):
        calls.append(delivery_id)
        time.sleep(0.15)
        return "provider-one-worker"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: news.process_one(sender=accepted), range(2)))
    assert sorted(results) == [False, True]
    assert len(calls) == 1


def signed_event(event, event_id, secret):
    body = json.dumps(event).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(base64.b64decode(secret[6:]), f"{event_id}.{timestamp}.".encode() + body, hashlib.sha256).digest()
    return body, {"svix-id": event_id, "svix-timestamp": timestamp, "svix-signature": "v1," + base64.b64encode(digest).decode()}


def test_verified_provider_events_are_idempotent_and_suppress_future_deliveries(client, monkeypatch):
    from app.routers import news as news_routes
    user = account(subscribed=True)
    assert login(client, account(role="admin")).status_code == 200
    publish(client)
    settings = replace(get_settings(), resend_webhook_secret="whsec_" + base64.b64encode(b"fixture signing secret").decode())
    monkeypatch.setattr(news_routes, "get_settings", lambda: settings)
    event = {"type": "email.complained", "data": {"email_id": "provider-complaint", "from": settings.smtp_from_email, "to": [user["email"]]}}
    body, headers = signed_event(event, "event-fixture", settings.resend_webhook_secret)
    assert client.post("/api/email/events/resend", content=body + b" ", headers=headers).status_code == 401
    assert rows("SELECT 1 FROM news_suppression") == []
    assert client.post("/api/email/events/resend", content=body, headers=headers).status_code == 200
    assert client.post("/api/email/events/resend", content=body, headers=headers).status_code == 200
    assert len(rows("SELECT 1 FROM news_provider_event")) == 1
    assert len(rows("SELECT 1 FROM news_suppression")) == 1
    assert news.process_one()  # The queued message is stopped without invoking transport.
    assert rows("SELECT status FROM news_delivery")[0]["status"] == "skipped"
    publish(client, title="After suppression")
    assert len(rows("SELECT 1 FROM news_delivery")) == 1
    assert login(client, user).status_code == 200
    assert client.get("/api/me/subscriptions").json()["status"] == "suppressed"


def test_provider_event_arriving_before_api_acknowledgement_is_preserved(client):
    user = account(subscribed=True)
    assert login(client, account(role="admin")).status_code == 200
    publish(client)
    def early_event(payload, delivery_id, **kwargs):
        with database.transaction() as (_, cur):
            news.record_provider_event(cur, "event-early", {
                "type": "email.delivered", "data": {"email_id": "provider-early", "from": get_settings().smtp_from_email, "to": [user["email"]]},
            })
        return "provider-early"
    assert news.process_one(sender=early_event)
    assert rows("SELECT status FROM news_delivery")[0]["status"] == "delivered"


def test_create_replay_returns_original_and_conflicts_are_scoped_to_editor(client):
    account(subscribed=True)
    first_editor = account(role="admin")
    assert login(client, first_editor).status_code == 200
    payload = {"title": "One saved publication", "body": "The full story", "status": "published",
               "email_introduction": "An invitation", "announce": True}
    assert client.post("/api/content/media", json=payload).status_code == 422
    assert rows("SELECT 1 FROM media_post") == []
    payload["request_id"] = str(uuid4())
    first = client.post("/api/content/media", json=payload)
    replay = client.post("/api/content/media", json=payload)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert len(rows("SELECT 1 FROM media_post")) == 1
    assert len(rows("SELECT 1 FROM news_announcement")) == 1
    assert len(rows("SELECT 1 FROM news_delivery")) == 1
    normalized = client.post("/api/content/media", json={**payload, "title": f"  {payload['title']}  ", "image_url": ""})
    assert normalized.status_code == 201 and normalized.json() == first.json()
    conflict = client.post("/api/content/media", json={**payload, "body": "Different content"})
    assert conflict.status_code == 409
    assert len(rows("SELECT 1 FROM news_delivery")) == 1
    # UUIDs belong to the authenticated editor. A different editor cannot replay
    # or conflict with the first editor's private create operation.
    assert login(client, account(role="admin")).status_code == 200
    independent = client.post("/api/content/media", json=payload)
    assert independent.status_code == 201
    assert independent.json()["media_post_id"] != first.json()["media_post_id"]
    assert len(rows("SELECT 1 FROM media_create_request")) == 2
    legacy = client.post("/api/content/media", json={"title": "Legacy news only", "body": "No announcement"})
    assert legacy.status_code == 201
    assert legacy.json()["announcement_queued"] is False


def test_concurrent_identical_create_requests_commit_one_announcement(client):
    account(subscribed=True)
    assert login(client, account(role="admin")).status_code == 200
    payload = {"title": "Concurrent publication", "body": "A full story", "status": "published",
               "email_introduction": "An invitation", "announce": True, "request_id": str(uuid4())}
    session = dict(client.cookies)
    def submit(_):
        with TestClient(create_app(initialize_services=False)) as other_client:
            other_client.cookies.update(session)
            response = other_client.post("/api/content/media", json=payload)
            return response.status_code, response.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(submit, range(2)))
    assert replies[0] == replies[1]
    assert replies[0][0] == 201
    assert len(rows("SELECT 1 FROM media_post")) == 1
    assert len(rows("SELECT 1 FROM news_announcement")) == 1
    assert len(rows("SELECT 1 FROM news_delivery")) == 1
    assert len(rows("SELECT 1 FROM media_create_request")) == 1


def test_failed_publication_does_not_consume_create_request(client, monkeypatch):
    from app.routers import content
    account(subscribed=True)
    assert login(client, account(role="admin")).status_code == 200
    payload = {"title": "Retry after rollback", "body": "A full story", "status": "published",
               "email_introduction": "An invitation", "announce": True, "request_id": str(uuid4())}
    original = content.queue_announcement
    def fail_queue(*args, **kwargs):
        raise RuntimeError("Fixture rollback")
    monkeypatch.setattr(content, "queue_announcement", fail_queue)
    with pytest.raises(RuntimeError, match="Fixture rollback"):
        client.post("/api/content/media", json=payload)
    assert rows("SELECT 1 FROM media_post") == []
    assert rows("SELECT 1 FROM media_create_request") == []
    monkeypatch.setattr(content, "queue_announcement", original)
    response = client.post("/api/content/media", json=payload)
    assert response.status_code == 201
    assert len(rows("SELECT 1 FROM media_post")) == 1
    assert len(rows("SELECT 1 FROM news_delivery")) == 1


def test_concurrent_distinct_create_requests_get_distinct_slugs(client):
    assert login(client, account(role="admin")).status_code == 200
    session = dict(client.cookies)
    def submit(_):
        with TestClient(create_app(initialize_services=False)) as other_client:
            other_client.cookies.update(session)
            return other_client.post("/api/content/media", json={
                "title": "Shared title", "body": "A story", "request_id": str(uuid4()),
            })
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(submit, range(2)))
    assert [response.status_code for response in replies] == [201, 201]
    assert len({response.json()["slug"] for response in replies}) == 2


def test_worker_rechecks_retry_window_after_waiting_for_account_lock(client, monkeypatch):
    user = account(subscribed=True)
    assert login(client, account(role="admin")).status_code == 200
    publish(client)
    rows("UPDATE news_delivery SET first_attempt_at = now() - interval '22 hours' RETURNING delivery_id")
    clock = [datetime.now(timezone.utc)]
    checked_before_lock = Event()
    def now(_):
        value = clock[0]
        checked_before_lock.set()
        return value
    monkeypatch.setattr(news, "datetime", SimpleNamespace(now=now))
    calls = []
    def accepted(*args, **kwargs):
        calls.append(True)
        return "provider-expired-key"
    with ThreadPoolExecutor(max_workers=1) as pool:
        with database.transaction() as (_, cur):
            cur.execute('SELECT user_id FROM "user" WHERE user_id = %s FOR UPDATE', (user["id"],))
            future = pool.submit(news.process_one, sender=accepted)
            assert checked_before_lock.wait(timeout=3)
            # Simulate a long operator transaction without an actual long sleep.
            clock[0] += timedelta(hours=2)
        assert future.result(timeout=5) is True
    assert calls == []
    assert rows("SELECT status FROM news_delivery")[0]["status"] == "uncertain"
