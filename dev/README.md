# UMST Docker button scripts

The project now uses Docker for local testing and deployment-style runs, while the `dev` folder gives you simple button-like scripts instead of one big CLI.

Each shell script in `dev/sh` has a matching Windows batch file in `dev/bat`.

## Button files

```text
dev/sh/load_env.sh          dev/bat/load_env.bat
dev/sh/local_testing.sh     dev/bat/local_testing.bat
dev/sh/deployment.sh        dev/bat/deployment.bat
dev/sh/health_check.sh      dev/bat/health_check.bat
dev/sh/certificates.sh      dev/bat/certificates.bat
dev/sh/permissions.sh       dev/bat/permissions.bat
```

There is also an internal helper pair:

```text
dev/sh/_common.sh           dev/bat/_common.bat
```

You normally do not run the `_common` files directly.

## Linux / Git Bash / WSL

First give the scripts permission to run:

```sh
chmod +x dev/sh/*.sh
```

Then run the button you want:

```sh
dev/sh/local_testing.sh
dev/sh/deployment.sh
dev/sh/health_check.sh
dev/sh/certificates.sh
dev/sh/permissions.sh
dev/sh/load_env.sh
```

## Windows cmd.exe

Double-click the `.bat` file you want, or run it from `cmd.exe`:

```bat
dev\bat\local_testing.bat
dev\bat\deployment.bat
dev\bat\health_check.bat
dev\bat\certificates.bat
dev\bat\permissions.bat
dev\bat\load_env.bat
```

## What each button does

### `load_env`

Loads `.env` and prints the important local URLs and project settings. The other scripts also load `.env` automatically.

On Bash, you may also source it if you want the variables in your current terminal:

```sh
source dev/sh/load_env.sh
```

### `local_testing`

This is the normal development setup with hot reload.

URLs:

```text
http://localhost:5173
http://localhost:5174/dashboard/profile/
http://localhost:8000
```

Use it for:

- starting local testing
- checking local containers
- viewing logs
- stopping local testing
- rebuilding local images
- resetting the local database/volumes

### `deployment`

This handles deployment-like actions.

For local deployment-style testing, it starts nginx on:

```text
http://localhost:8080
```

It can also run remote deployment actions:

- remote setup Docker/certbot
- remote full deploy
- remote upload only
- remote start only
- remote stop only
- remote shell

The remote target is chosen as `COM` or `CN` when the script asks.

### `health_check`

Checks one of:

- local hot-reload Docker stack
- local nginx deployment-style stack
- remote COM stack
- remote CN stack

### `certificates`

Renews or issues certificates for COM/CN.

`CERT_MODE=standalone` runs the standalone certbot flow remotely.

`CERT_MODE=manual` opens SSH and prints the manual DNS certbot command.

### `permissions`

Keeps permissions easy to reach.

It can:

- give local `dev/sh/*.sh` execute permission
- fix remote COM permissions
- fix remote CN permissions

## Docker files

The scripts are intentionally thin. Most local/deployment configuration lives in:

```text
docker/backend.Dockerfile
docker/compose.local.yml
docker/compose.deploy.yml
docker/nginx.deploy.conf
```

The safe defaults live in `.env`. Put real private remote secrets only in your own local/server copy of `.env`.
