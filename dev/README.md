# Operation scripts

The Windows `bat/` wrappers and Bash `sh/` scripts provide local operation, remote observation, deployment, certificates and account promotion. Shared Bash implementation lives in `_common.sh`. Scripts read the repository environment and select LOCAL, COM or CN.

`local_testing` runs hot-reload Compose actions. `deployment` includes local deployment-style actions and remote actions. `agent_deploy.sh` performs the reviewed update with a verified backup SHA-256; it is not first provisioning. `agent_observe_remote.sh` reads container status and logs. `health_check` checks the selected environment. `certificates` handles the existing issuance path; renewal differences are documented separately.

Dockerfiles belong to `backend/python/` and all three frontend directories: `webpage/`, `dashboard/`, `demo/`. Root Compose files retain stable relative paths. The internal proxy configuration is under `config/`; host COM/CN Nginx configurations remain separate because their domains differ.

Read [operations](../docs/operations.md) before running a mutation, [release identity](../docs/releases.md) before publication/deployment, and [certificate renewal](../docs/certificate-renewal.md) for renewal. [RUN.md](RUN.md) retains useful current operating findings. Authorization already provided by the active task applies to its named environment.
