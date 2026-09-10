---
name: theumst-debug
description: Diagnose Theumst failures using relevant source, logs, state and tests.
---

# theumst-debug

Paths below are relative to the Theumst repository root. Start with [README.md](../../../README.md) and follow [AGENTS.md](../../../AGENTS.md).

1. Read the affected component README/RUN and its architecture or behavior page.

2. Reproduce the reported failure with an observable expected and actual outcome. Inspect the owning request, state and storage path.

3. Test the smallest supported explanation. Apply an authorized repair and verify the original failure and relevant regressions.

4. Record the cause, changed behavior, checks and unresolved conditions. Keep secrets and raw diagnostics out of current documentation.
