# Data architecture

PostgreSQL is authoritative for users, roles/access, sessions, keys, books, sections, knowledge objects, language-specific content, crystals, semantic projection metadata and study state. Qdrant stores vectors addressed by embedding identity. Storage adapters hold image bytes, with `book_image` connecting them to books and objects.

Books use `grimoire_id`, sections use `section_id`, and source-specific knowledge uses `knowledge_id`. Source keys identify publisher data for updates. A book version is its published edition/version. Crystal membership uses `knowledge_crystal_id`; the preferred instance is marked by `is_default_in_crystal`. Crystallization reads membership directly and filters hidden sources.

`user_grimoire` holds a user's summoned books. `demo_knowledge_progress` has one completion row per user/object. `demo_study_state` preserves independent Text and Questions positions. Hiding a book changes reader visibility without deleting these rows. `demo_note` permits multiple attached notes and separate scribbles. Hidden source labels and links are withheld while the user's writing remains readable. Deletion is different and follows existing foreign-key actions.

The complete compact reader list orders active objects by demo override, canonical source-order metadata, then ID. Continue and the gold path use that list without filtering completed objects or exercises. The local display may omit positions but never changes the underlying order.

Two authored relation stores currently exist: legacy `relation` allows one type per ordered object pair and can cross books; graph-sidecar tables allow typed book-scoped edges and multiple types. The sidecar validator rejects directed cycles. The existing demo graph endpoint generates `book_order_v1` with `authored_dependencies: false`; it does not establish authored dependencies. The Atlas only uses explicitly authored data for dependency distance and arrows.

[Settle the full Whole-book upload and integration route](https://github.com/Christopher8187/product/issues/30) owns producer fields, type/direction meaning, revisions, missing/invalid data, cycle treatment, cross-book mapping and connection of authored relations to the reader. Its existing implementation and verification tasks follow the earlier release. They must read this page, [ingestion](../ingestion.md) and [Atlas](../atlas.md). No dependency on that later route is added to 0.1.0.

Schema updates use the reviewed migration runner described in [operations](../operations.md). Shared definitions remain in the Parent Repo context map linked from [CONTEXT.md](../../CONTEXT.md).
