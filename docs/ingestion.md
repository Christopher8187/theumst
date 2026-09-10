# Whole-book upload

A master publishing key submits an archive to `/api/v1/books/ingest-archive`. The proxy applies a route-specific one-GiB request limit. The backend validates the archive and manifest, resolves source identities, writes book/section/knowledge data, manages semantic projections and vectors, and stores image content through the selected adapter. Publisher metadata can overwrite the fields it owns on later uploads.

`services/book_ingestion.py` owns archive processing; `services/knowledge.py` owns lower-level knowledge/embedding submission; `services/graph_sidecar.py` validates and persists optional authored graph data. Read their current schemas and tests before changing accepted fields. Image storage and Qdrant operations do not share PostgreSQL's transaction, so current failures can leave partial external results. Receipt and retry behavior must be verified against the actual chosen path.

Current graph-sidecar storage is book-scoped and validates cycles. The demo's generated order graph is a different representation. [Data architecture](architecture/data.md) records the distinction.

[Settle the full Whole-book upload and integration route](https://github.com/Christopher8187/product/issues/30) owns Kaicenat-produced dependency fields, direction/types, source identities, revisions, empty/missing/invalid data, storage mapping and reader requirements. Its [implementation](https://github.com/Christopher8187/product/issues/66) and [verification](https://github.com/Christopher8187/product/issues/67) follow the earlier Theumst release. Each must read this document, [data architecture](architecture/data.md), [Atlas](atlas.md) and the accepted functional decisions.

Use the [database ingestion tests](../backend/python/tests/README.md) against an explicitly disposable database. A fake cursor can validate query construction, but cannot establish rollback, constraints, external writes or end-to-end publication.
