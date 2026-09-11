# Application architecture

The public site and dashboard are separate Vue builds that share the desktop, background, windows and Profile. Public windows present learning information, News and account forms. Signed-in dashboard tools provide API keys and permitted management pages. The Web Demo is a third, unchanged Vue build containing the library, realm selection and study interface. [Frontend architecture](frontend.md) describes their state and navigation.

FastAPI serves the public and dashboard build outputs, owns authenticated APIs and publishes health endpoints. In deployment, host Nginx terminates TLS and forwards to the loopback-bound internal proxy. That proxy serves `/demo/` from the isolated demo container after an auth subrequest to `/api/demo/auth-check`. Requests under `/api/` reach the backend. API failures must remain API responses instead of falling through to a Vue page.

PostgreSQL contains accounts, permissions, published content and study data. Qdrant is a separate vector service. Object storage is selected by environment. COM and CN retain independent policies, permitted books and credentials. No synchronization procedure is selected between them.

Startup validates PostgreSQL readiness without changing a production schema. It may initialize Qdrant collection settings and reports degraded Qdrant availability separately. A process listening on its port does not establish that storage, authentication or publishing works. [Testing](../testing.md) distinguishes those checks.

Docker Compose files define local hot reload and deployment service arrangements. [Operations](../operations.md) owns how to start, update and recover them. Backend code organization is in [backend architecture](backend.md); [data architecture](data.md) owns identities and persistence boundaries.
