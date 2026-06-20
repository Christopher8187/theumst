# UMST Docker dev scripts

The project is now Docker-first. The shell scripts are small wrappers around Docker Compose.

## Folder layout

```text
dev/sh/   Linux/macOS/Git Bash scripts
dev/bat/  Windows cmd.exe scripts
docker/   Dockerfiles, Compose files, and nginx config
```

## Local hot-reload testing

This is the everyday development setup. It starts Postgres, FastAPI, the public webpage Vite app, and the dashboard Vite app.

```sh
chmod +x dev/sh/*.sh
dev/sh/activate_local_server.sh
```

Open:

```text
http://localhost:5173
http://localhost:5174/dashboard/profile/
http://localhost:8000
```

Windows cmd.exe:

```bat
dev\bat\activate_local_server.bat
```

## Deployment-style nginx test

This builds the Vue apps, bakes them into the FastAPI image, then puts nginx in front.

```sh
dev/sh/activate_deploy_stack.sh
```

Open:

```text
http://localhost:8080
```

## Stop

```sh
dev/sh/stop_local_server.sh
dev/sh/stop_deploy_stack.sh
```

## Reset local database/storage

```sh
dev/sh/reset_local_server.sh
```

This deletes Docker volumes for the local testing stack.

## Remote deployment

Fill the remote values in `.env`, then run:

```sh
dev/sh/initialize_remote_server.sh
dev/sh/upload_all_to_server.sh
dev/sh/activate_remote_server.sh
```

The remote scripts now install/use Docker and run the deployment Compose file instead of creating Python venvs, running npm directly, and managing a systemd backend service.
