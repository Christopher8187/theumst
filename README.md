# Theumst 0.1.0

Theumst turns structured books into a reader with saved study positions, shared completion, personal notes and discovery across available books. A reader signs in on the public site, requests Web Demo access from the dashboard, summons a grimoire and enters Text, Notes or Questions. The other realm entries describe future learning activities and currently show a coming-soon message.

The public site, signed-in dashboard and protected Web Demo are three separate Vue applications. One FastAPI backend handles accounts, permissions, content management, study state and publishing. PostgreSQL holds book structure and user state; Qdrant holds semantic vectors; book images use local storage, DigitalOcean Spaces on COM or Aliyun OSS on CN. The internal Nginx proxy checks Web Demo access before serving its separate container. Read [application architecture](docs/architecture/application.md) for request paths and [data architecture](docs/architecture/data.md) for ownership.

## Common work

For an existing configured local installation, start Docker, then run `dev/bat/local_testing.bat` or `dev/sh/local_testing.sh`. Inspect the current menu before selecting an action. The hot-reload applications use ports 5173, 5174 and 5175, with the backend on 8000. Fresh databases require explicit initialization. Ordinary startup does not replay historical migrations. [Operations](docs/operations.md) explains first setup, existing databases and the deployment procedure.

Read [CONTEXT.md](CONTEXT.md) for Theumst meanings and its link to shared knowledge definitions. The [Web Demo behavior](docs/web-demo.md) explains reading, notes, hidden material and discovery; [Atlas](docs/atlas.md) explains the two graph views and navigation. The component guides describe source organization: [backend](backend/README.md), [frontends](frontend/README.md), and [operation scripts](dev/README.md).

Content managers use dashboard Books and Media. [Administration](docs/administration.md) explains hiding, deletion and roles. Publishers use the master-key [Whole-book upload](docs/ingestion.md). Read [security](docs/security.md) before changing access or publishing keys and [account recovery](docs/account-recovery.md) for SMTP and reset behavior.

Before publishing an update, follow [testing](docs/testing.md), [release identity](docs/releases.md) and [operations](docs/operations.md). COM and CN have independent data and settings. The 0.1.0 delivery targets COM only. The [0.1.0 release record](https://github.com/Christopher8187/theumst/releases/tag/v0.1.0) records publication, verification and the deployed COM revision.

Agent reading paths and repository procedures start in [AGENTS.md](AGENTS.md). Current explanations live under `docs/`; [historical material](docs/history/README.md) and [proposed graph effects](docs/plans/graph-effects.md) are separate from current behavior.
