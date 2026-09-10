---
name: theumst-test
description: Verify Theumst backend, frontends, databases, performance and browser behavior.
---

# theumst-test

Paths below are relative to the Theumst repository root. Start with [README.md](../../../README.md) and follow [AGENTS.md](../../../AGENTS.md).

1. Read docs/testing.md, affected test READMEs and relevant objectives before selecting checks.

2. Use isolated local fixtures. Run relevant deterministic checks first, then real backend/database checks and affected builds. A coordinated release builds all three frontends.

3. For the 0.1.0 acceptance procedure, coordinate six Sol/medium agents as docs/testing.md specifies. Record initial states and observable outcomes from docs/testing/web-demo.md.

4. Keep simulated, local real-backend and COM-derived results separate. Record revision, commands, setup, outcomes, skips and remaining failures. Complete verification only when the required checks pass or clearly report their unmet conditions.
