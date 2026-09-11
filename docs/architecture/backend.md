# Backend architecture

`backend/python/app/main.py` builds FastAPI, installs CORS and compression, mounts public branding images, and includes the routers. `app.py` at the Python root is a compatibility entry; the container uses `app.main:app`.

Routers separate accounts, user profile, API keys, content, Web Demo, admin tools, superadmin tools, public publishing/reading, health and frontend delivery. `dependencies.py` authenticates sessions and keys and checks database-backed access. A hidden frontend button is never the authorization boundary.

Services own storage adapters, knowledge persistence, Whole-book upload, graph sidecars, email, Qdrant access and semantic discovery. `database.transaction()` opens a PostgreSQL connection, commits on success and rolls back on error. External vector/image writes do not share that transaction; see [ingestion](../ingestion.md).

`routers/news.py` handles personal subscriptions, authorized email preview, unsubscribe confirmation and verified provider events. `services/news.py` owns explicit consent, the publication outbox, Resend delivery retries and suppression; `services/email.py` renders all four email types. The optional lifespan worker uses PostgreSQL leases and saved provider idempotency keys. [News subscriptions](../news-subscriptions.md) owns API behavior and delivery limits.

`services/media_creation.py` wraps editorial creation in a persistent request identity scoped to its editor. The response and normalized payload fingerprint commit with the post and any announcement, so a lost creation response can be retried safely. Conflicting reuse returns 409; creating an announcement requires a UUID while legacy news-only creation remains compatible.

Web Demo routes require the Web Demo access point. Reader queries filter book visibility and active knowledge. Personal writing belongs to its user independently of source availability. Publishing and administration retain their own authorized routes. Read [security](../security.md) before changing these distinctions.

Schema source lives in `backend/sql`. `reviewed_migrations.py` checks file hashes, baseline markers, applied schema markers and partial application. The explicit migration runner requires a verified backup digest. Backend lifespan calls the readiness check by default; historical replay is restricted to an explicitly configured local environment. [Operations](../operations.md) owns commands.

The [backend README](../../backend/README.md) lists source entry points. [Test modules](../../backend/python/tests/README.md) explain actual service/database coverage.
