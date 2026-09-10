---
name: theumst-operate
description: Run, deploy, restore or renew certificates for the selected Theumst environment.
---

# theumst-operate

Paths below are relative to the Theumst repository root. Start with [README.md](../../../README.md) and follow [AGENTS.md](../../../AGENTS.md).

1. Read docs/operations.md, dev/README.md and dev/RUN.md. Read docs/releases.md for publication/deployment and docs/certificate-renewal.md for certificates.

2. Confirm the target from the active request and inspect current scripts and runtime state. Preserve authorization already given; the requested 0.1.0 COM deployment does not require another approval.

3. For deployment, verify the backup by restoration, record its digest and use the exact published source. Preserve selected environment data/configuration and follow the reviewed migration procedure.

4. Check the resulting runtime and record deployed revision, health, access and reader observations. If an operation fails, retain evidence and recover within the authorized boundary; do not expand into an unrelated environment or destructive reset.
