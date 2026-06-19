# UMST dev shell scripts

The old Windows `.bat` scripts have been replaced with portable `dev/*.sh` scripts.

## Linux local path

This project is configured for the Linux laptop path:

```sh
/home/christopher/Desktop/theumst
```

If the project is somewhere else, the scripts automatically fall back to the folder they are running from.

## First run on Linux

```sh
cd /home/christopher/Desktop/theumst
chmod +x dev/*.sh
dev/initialize_local.sh
dev/activate_local_nginx_server.sh
```

Open `http://localhost:8080`.

## Windows

Run the same `.sh` scripts from Git Bash or WSL. Native `cmd.exe` will not run `.sh` files.

## Remote target

`.env` now uses:

```env
SERVER=LOCAL
REMOTE_SERVER=COM
```

`SERVER=LOCAL` keeps the local backend on local file storage. Remote scripts deploy to `REMOTE_SERVER`, which can be `COM` or `CN`.

## Restart local server on Windows Git Bash

```sh
cd /c/Users/Chris/Desktop/theumst
bash dev/stop_local_nginx_server.sh
bash dev/activate_local_nginx_server.sh
bash dev/check_local_nginx_server.sh
```

If Nginx reports missing `.local/nginx/logs` or `.local/nginx/temp/...`, this version creates those folders automatically before testing the config.
