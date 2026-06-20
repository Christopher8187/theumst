# Docker setup

The Docker setup has been moved so it does not depend on the current path of the `dev/sh` or `dev/bat` scripts.

The two Compose files now live at the project root:

```text
compose.local.yml
compose.deploy.yml
```

Each app project owns its own Dockerfile:

```text
backend/python/Dockerfile
frontend/webpage/Dockerfile
frontend/dashboard/Dockerfile
```

Compose always builds from the repository root with stable paths, so the scripts can be launched from Linux, Git Bash, WSL, or Windows without changing Dockerfile paths.

## 1. Local testing: `compose.local.yml`

Services:

- `db` — PostgreSQL with `backend/sql/schema.sql` loaded on first run.
- `backend` — FastAPI on `http://localhost:8000`, mounted with live source code.
- `webpage` — Vite public site on `http://localhost:5173`.
- `dashboard` — Vite dashboard on `http://localhost:5174`.

Run on Linux / Git Bash / WSL:

```sh
chmod +x dev/sh/*.sh
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

Run on Linux / Git Bash / WSL:

```sh
./dev/sh/deployment.sh
```

Run on Windows:

```bat
dev\bat\deployment.bat
```

For a real server, set `HTTP_PORT=80` in `.env` or your shell before starting the stack.

## Direct Compose commands

The button scripts are still the recommended entry point, but these also work from the project root:

```sh
docker compose -f compose.local.yml up --build -d
docker compose -f compose.deploy.yml up --build -d
```

## Build caching

The Dockerfiles copy package/requirements files before source files so Docker can cache `npm ci` and `pip install`. They also use BuildKit cache mounts for npm and pip caches.

## Secrets

Safe placeholders live in `.env.example`. Copy it to `.env` and put real private remote secrets only in your own local/server copy of `.env`.
