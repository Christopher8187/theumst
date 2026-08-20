# Theumst Agentic File System Routing instructions

## Shared definitions

Read `C:\Business\product\docs\definitions.md` before planning Product Workspace
directory or multi-repository work, referring to another Product Workspace
repository, changing Agentic File System Routing, or interpreting an unfamiliar
Product Workspace term.

A narrow Theumst implementation, diagnosis, or bug fix may stay inside this
repository without loading the shared definitions when its source changes and
verification remain here and no shared term is unclear. When uncertain, read
the definitions.

Christopher chooses Product Workspace terms. If a needed concept is absent from
the definitions, explain the missing distinction and ask Christopher to provide
the term and meaning.

## Work in this repository

For repository-local work, use Theumst backend, frontend, deployment code,
tests, and documentation from this worktree. Do not infer current files or
runtime state from another Theumst worktree.

If Theumst work requires a change in another Product Workspace repository,
stop before editing that repository and ask Christopher. Name this repository,
the additional repository, why it is needed, and the exact action proposed.

Ask Christopher before changing a running production system or its live data,
infrastructure, credentials, or deployed version.
