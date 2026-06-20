# Docker setup

There are two Docker configurations.

## 1. Local testing: `docker/compose.local.yml`

Services:

- `db` — PostgreSQL with `backend/sql/schema.sql` loaded on first run.
- `backend` — FastAPI on `http://localhost:8000`, mounted with live source code.
- `webpage` — Vite public site on `http://localhost:5173`.
- `dashboard` — Vite dashboard on `http://localhost:5174`.

Run:

```sh
dev/sh/activate_local_server.sh
```

Windows:

```bat
dev\bat\activate_local_server.bat
```

## 2. Deployment-style: `docker/compose.deploy.yml`

Services:

- `db` — PostgreSQL.
- `backend` — production FastAPI image with both Vue apps already built into it.
- `nginx` — small public reverse proxy on `http://localhost:8080` by default.

Run:

```sh
dev/sh/activate_deploy_stack.sh
```

For a real server, set `HTTP_PORT=80` in `.env` or your shell before starting the stack.

## Build caching

`docker/backend.Dockerfile` copies package files before source files so Docker can cache `npm ci`. It also uses BuildKit cache mounts for npm and pip caches.

## Secrets

The returned `.env` is safe for local Docker testing and has remote/cloud secrets blanked. Put real server passwords and storage API keys back into your private `.env` on your own machine/server.
