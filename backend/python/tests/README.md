# Backend tests

Run `python -m pytest tests` from `backend/python` after installing `requirements-dev.txt`. Use LOCAL configuration and isolated service addresses. On Windows put Git for Windows `bin` before System32 in PATH so shell checks use Git Bash rather than the WSL launcher.

The endpoint and service unit tests use scripted cursors or HTTP transports. They check authentication order, data filtering, error behavior, ingestion validation, account/token handling and deployment guards without establishing database persistence. `test_similar_retrieval.py` covers the retained single-book endpoint and crystallization; `test_discovery.py` covers the current cross-book discovery service. `test_reviewed_migrations.py` checks pinned sources and refusal of partial state.

`test_book_ingestion_database.py` requires `THEUMST_DATABASE_INTEGRATION=1`. It inserts real books, nested sections, objects and projection metadata in PostgreSQL, checks returned identities, then rolls back. It does not send vectors to Qdrant. Its default skip must be reported separately. Conftest import fallbacks are for unit tests; a real-service run must have actual psycopg2 and password hashing dependencies installed.

Release acceptance also exercises the current endpoints against PostgreSQL and Qdrant, independent realm positions, hidden-source note persistence, and real schema upgrade/fresh initialization. The [browser objectives](../../../docs/testing/web-demo.md) describe observable flows; [testing](../../../docs/testing.md) owns evidence requirements. Keep temporary users, vectors and databases separate from production.
