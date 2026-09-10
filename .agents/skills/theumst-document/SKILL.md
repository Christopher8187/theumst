---
name: theumst-document
description: Maintain Theumst explanations, reading paths and current RUN findings.
---

# theumst-document

Paths below are relative to the Theumst repository root. Start with [README.md](../../../README.md) and follow [AGENTS.md](../../../AGENTS.md).

1. Read docs/documentation.md and the active decision. Inspect affected source/tests before asserting behavior.

2. Update the single owning explanation and its inbound reading links. Keep definitions in CONTEXT.md, current operating knowledge in RUN and dated history under docs/history.

3. Compare current claims adversarially with source. Resolve stale or contradictory claims and validate local links. Do not run code tests solely for Markdown.

4. Synchronize authoritative AGENTS.md and CONTEXT.md to existing Theumst linked worktrees as required by AGENTS.md. Report remaining inconsistencies without presenting intended behavior as verified runtime state.
