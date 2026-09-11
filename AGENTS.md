# Theumst agent entry point

Read README.md, relevant CONTEXT.md definitions, the affected architecture or behavior documents, affected component READMEs and current RUN notes, then source and tests. Informational requests may stop when those sources answer the question. Use an instruction-only repository skill when its procedure matches the request.

## Required reading

| Work | Read |
| --- | --- |
| Architecture or work crossing application areas | docs/architecture/application.md and the relevant backend, frontend and data pages; affected component READMEs. |
| Desktop windows, entry URLs, account links or stale website builds | docs/architecture/frontend.md, frontend/shared/README.md and docs/architecture/backend.md; docs/operations.md for live serving checks. |
| Web Demo reading, notes, completion, language, ranking or navigation | frontend/demo/README.md, docs/web-demo.md, docs/architecture/data.md, docs/testing/web-demo.md. |
| Atlas layout, arrows, selection, Continue or gap counts | docs/atlas.md, docs/architecture/data.md, frontend/demo/README.md, docs/testing/web-demo.md. |
| Authentication, keys, hiding, deletion or administration | docs/security.md, docs/administration.md, docs/architecture/backend.md, docs/architecture/data.md and relevant tests. |
| Recovery or SMTP | docs/account-recovery.md, docs/security.md, backend/README.md and relevant tests. |
| Ingestion, schema, authored relations or integration | docs/ingestion.md, docs/architecture/data.md and the linked current shared integration decision. |
| Run, deploy, restore or certificates | docs/operations.md, dev/README.md, dev/RUN.md, docs/releases.md; docs/certificate-renewal.md for certificates. |
| Verification or performance | docs/testing.md, affected test READMEs/objectives and theumst-test. |
| Documentation | docs/documentation.md, affected source/tests and theumst-document. |

## Procedures

Skills live under `.agents/skills/<name>/SKILL.md`. Use `theumst-design-new-architecture` for a new application area, `theumst-modify-architecture` for a selected change, and `theumst-analyze-architecture` for assessment before selecting changes. Use `theumst-test` for verification, `theumst-operate` for operation, `theumst-debug` for diagnosis and `theumst-document` for documentation maintenance.

When documentation and source disagree, record intended behavior, observed behavior with supporting source, provisional assumptions and affected decisions. Continue unaffected work. Accepted functional decisions govern their implementation. Bring unresolved meaning to Christopher; do not turn a source defect into a new product definition.

## Working boundaries

Read `C:\Business\product\CONTEXT-MAP.md` before Parent Repo directory work, multi-repository work, AFSR changes, references to another repository or replies about Parent Repo files. Follow its linked operating guide. Preserve dirty files, ignored runtime data and existing linked-worktree state. Use source from this worktree; another worktree does not establish its runtime state.

The normal direct child directory holds authoritative AGENTS.md and CONTEXT.md. Apply settled changes there first and synchronize these two files to every existing Theumst linked worktree. Do not merge unrelated source solely for synchronization. Create additional working directories only when Christopher requests them.

Production changes require Christopher's authorization. Preserve authorization already supplied by the active task and its selected environment; do not ask again for the requested COM deployment in the 0.1.0 task. Unrelated infrastructure, CN deployment and live-data changes remain outside that request. Before a repository-local task requires editing another repository, follow the Parent Repo permission boundary.
