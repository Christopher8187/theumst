# Docker setup

The project has two root-level Compose files:

```text
compose.local.yml              # safe local hot-reload stack
compose.deploy.yml             # real deploy stack with current secrets, gitignored
compose.deploy.example.yml     # safe template for git
```

Each app project owns its own Dockerfile:

```text
backend/python/Dockerfile
frontend/webpage/Dockerfile
frontend/dashboard/Dockerfile
```

Compose always builds from the repository root with stable paths, so scripts can be launched from Linux, Git Bash, WSL, or Windows without changing Dockerfile paths.

## 1. Local testing: `compose.local.yml`

Services:

- `db` — PostgreSQL with `backend/sql/schema.sql` loaded on first run.
- `backend` — FastAPI on `http://localhost:8000`, mounted with live source code.
- `webpage` — Vite public site on `http://localhost:5173`.
- `dashboard` — Vite dashboard on `http://localhost:5174`.

Run on Linux / Git Bash / WSL:

```sh
chmod +x dev/sh/*.sh
./dev/sh/linux_first_fix.sh
newgrp docker
./dev/sh/local_testing.sh
```

Run on Windows:

```bat
dev\bat\local_testing.bat
```

## 2. Deployment-style: `compose.deploy.yml`

Services:

- `db` — PostgreSQL.
- `backend` — production FastAPI image with both Vue apps already built into it.
- `nginx` — small public reverse proxy on `http://localhost:8080` by default.

The deploy Compose file intentionally contains the current deployment secrets so the app works immediately. It is ignored by git. Use `compose.deploy.example.yml` as the tracked template.

Run on Linux / Git Bash / WSL:

```sh
./dev/sh/deployment.sh
```

Run on Windows:

```bat
dev\bat\deployment.bat
```

For a real server, set `HTTP_PORT=80` in your shell or `.env` before starting the stack.

## Direct Compose commands

```sh
docker compose -f compose.local.yml up --build -d
docker compose -f compose.deploy.yml up --build -d
```

## Assets

Images now live in:

```text
backend/assets/images/
```

The backend serves them at `/images/...`. Both Vue apps use `VITE_ASSET_BASE=http://localhost:8000/images` during local development.

## Secrets

`.env` is now only for scripts that need server connection details. Local app defaults live in `compose.local.yml`; deploy app credentials live in the gitignored `compose.deploy.yml`.

After rotating credentials, update `compose.deploy.yml` and your private `.env` copies, not the example files.
