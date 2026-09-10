# Operations

Use this guide for LOCAL, COM and CN. Environment-specific domains, storage and permitted books stay in configuration and their owning documents. Preserve authorization already supplied by the task. The combined 0.1.0 task requests COM deployment after verified main publication; unrelated production changes require Christopher's authorization.

## Local setup and existing data

Use `.env.example` as the list of required settings and retain secrets only in the working environment. Install Docker and Compose, and use the root `compose.local.yml` for hot reload. The three frontends run on 5173, 5174 and 5175; FastAPI runs on 8000. The deployment-style internal proxy uses the configured loopback HTTP port.

Remote packaging uses `DB_PASSWORD_COM` or `DB_PASSWORD_CN` when supplied, falling back to `DB_PASSWORD` for existing configurations. The replacement COM database has its own generated password. Keep that private setting with the retained environment before future updates. Production containers restart unless explicitly stopped and retain at most three 10 MB log files each. The production Qdrant version is pinned to the tested 1.17.0 release.

An existing database must pass the reviewed readiness check before startup. A fresh disposable LOCAL database can be initialized by explicitly setting `SERVER=LOCAL` and `DB_SCHEMA_STARTUP_MODE=replay` for `initialize_database()`. Historical replay runs the baseline before numbered SQL and includes old seeds; never use it on production or an existing database merely to satisfy startup. Return to disabled replay for normal operation. A local release check should use its own Compose project, database, ports and volumes.

Use `docker compose --env-file .env -f compose.local.yml ps` to inspect and `up --build -d` for the configured existing local stack. `down` stops containers while preserving named volumes. Volume deletion is a separate destructive operation requiring explicit scope. [Testing](testing.md) explains disposable verification.

## Fresh COM provisioning

The replacement COM target is 167.71.20.50, not the destroyed 165.227.23.136. The Parent Repo `docs/theumst-droplet-deployment-handoff.md` records the verified SSH key/host, DNS and initial resources. Normal application root remains `/var/www/theumst.com`. Bootstrap through root, then verify the retained `chris` deployment account and sudo access.

Christopher selected a fresh database on 10 September 2026. Preserve recovered Spaces objects; they do not restore PostgreSQL or Qdrant. Install Docker Engine/Compose using the official Ubuntu repository, Nginx and Certbot. Allow 22/80/443, keep the internal proxy loopback-only, and expose no database/vector port publicly. The small server uses swap; record actual memory, disk and response behavior before declaring capacity sufficient.

Use the tracked `compose.deploy.yml` (or its matching example when provisioning another checkout) with private environment settings. The example mounts only `backend/sql/schema.sql` for first PostgreSQL initialization; it does not replay historical seeds. Start the database and Qdrant dependencies, validate readiness, take a custom-format dump of that initialized state, restore it into a disposable verification database, and verify its SHA-256. This provides a fresh-install recovery baseline without claiming recovery of old user data.

Deploy the exact published source and recorded build artifacts. First startup must include dependencies; the established-server `--no-deps` update command is insufficient. Configure the host proxy after issuing the `theumst-com` certificate for both hostnames. Follow [certificate renewal](certificate-renewal.md), then check health, access, static assets, restart behavior, resource use and backup retention. Record any bootstrap-specific command and the source/artifact identity in release evidence.

## Backup and release update

Inspect the selected server read-only before deployment. Record its source revision, running services, database names, migration state, storage mode and existing previous release. Preserve the remote environment and deployment configuration. Verify that local target configuration matches those retained settings before uploading; the current packager builds its target environment from local settings.

Create a PostgreSQL custom-format dump and restore it into a disposable verification database. Check required tables, representative row counts and the migration state after restoration. Save and independently verify its SHA-256. Retain secure copies of the current source/configuration and the corresponding Qdrant/storage recovery information. Keep backups outside public release assets. Record backup identity, date, verification commands and result. A syntactically valid digest alone does not establish a usable backup.

After [release verification and publication](releases.md), run `dev/sh/agent_deploy.sh COM <verified-backup-sha256>` from the exact published source. The Windows wrapper accepts the corresponding argument. The task selects the environment; do not deploy CN as part of COM work.

The script transfers one compressed archive, retains the previous remote source tree, applies only missing reviewed migrations using the new image, starts backend/demo without recreating database/vector dependencies, then recreates the internal proxy so it resolves the current backend address. Read current `_common.sh` before relying on this sequence. A retained `.previous` tree blocks another update and must be resolved deliberately after verification.

Record the deployment artifact SHA-256 and source revision. Check root page, `/health`, `/health/db`, `/health/qdrant`, `/health/assets` and `/health/storage`, the protected demo access path and representative authenticated reading. Match the deployed revision to the annotated release tag. A static homepage check does not establish study persistence or visibility.

## Recovery and troubleshooting

On failed application startup, retain logs and both source trees. Inspect Compose status, backend schema errors, internal-proxy upstream resolution and dependency health. Restore the previous application tree only after confirming its compatibility with the current schema. Restore PostgreSQL from the verified backup only when a live-data rollback is explicitly authorized; restoring source alone does not undo SQL changes.

SSH connection timeout means remote state was not inspected. A missing Docker engine is a local runtime problem; simulated service tests cannot replace database checks. [Certificate renewal](certificate-renewal.md) owns COM/CN renewal differences. [Backend RUN](../backend/RUN.md) and [dev RUN](../dev/RUN.md) retain useful current operating findings.
