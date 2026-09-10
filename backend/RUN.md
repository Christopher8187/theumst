# Current backend operating notes

Backend startup validates the reviewed schema when `DB_SCHEMA_STARTUP_MODE=disabled`. Fresh local databases need explicit initialization; changing documentation does not require a pytest run.

The 0.1.0 study-position migration adds `questions_knowledge_id`. Apply it through the reviewed runner after verifying the selected database backup. Existing Text positions and completion rows remain intact.

The new neighbor route uses stored statement/combined projections with compatible model, collection, language and dimensions. It makes no embedding-provider call. Missing embeddings despite available workings are processing faults. [Testing](../docs/testing.md) records verification boundaries; release-specific outcomes belong in the release evidence rather than accumulating here.
