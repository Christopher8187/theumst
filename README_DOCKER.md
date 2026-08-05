# Docker quick reference

The complete source-to-live instructions are in [`README.md`](README.md).

Local development:

```bash
docker compose --env-file .env -f compose.local.yml up --build -d
```

Production-style stack on the current machine:

```bash
docker compose --env-file .env -f compose.deploy.yml up --build -d
```

Remote COM deployment:

```bash
./dev/sh/agent_deploy.sh COM
```

Remote CN deployment:

```bash
./dev/sh/agent_deploy.sh CN
```
