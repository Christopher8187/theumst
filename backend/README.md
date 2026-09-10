# Backend

The backend accepts account, study and publishing requests and coordinates PostgreSQL, vectors and image storage. It also serves the public-site and dashboard build outputs. The protected Web Demo has a separate frontend container.

Read [backend architecture](../docs/architecture/backend.md) before changing router/service boundaries and [data architecture](../docs/architecture/data.md) before changing persisted behavior. The Python package is `python/app`; `main.py` composes it, `routers/` handles HTTP boundaries, `services/` performs storage and domain work, and `schemas.py` validates payloads. SQL source is under `sql/`.

Use [operations](../docs/operations.md) for setup/startup and [RUN.md](RUN.md) for current operating findings. Run the relevant modules from [the test guide](python/tests/README.md); importing a route with stubbed dependencies does not establish PostgreSQL or Qdrant behavior.

The [Real Analysis demo sample](examples/real-analysis-demo/README.md) packages the saved Section Atlas material for Whole-book upload without changing the application or its schema.
