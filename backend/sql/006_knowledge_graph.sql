-- Optional, versioned knowledge-graph sidecar support for existing databases.
--
-- This migration intentionally matches the corresponding schema.sql block.
-- Existing books remain "unavailable" until a separately reviewed sidecar
-- explicitly supplies stable identities, semantic roles, and relations. No
-- relationship is inferred from source order, object type, proximity,
-- references, visualization needs, or embedding similarity.
--
-- Release blocker: graph semantics and ingestion/archive receipt changes need
-- Knowledge HEAD approval before this migration is applied to any database.

ALTER TABLE grimoire ADD COLUMN IF NOT EXISTS graph_contract_version int;
ALTER TABLE grimoire ADD COLUMN IF NOT EXISTS graph_revision text NOT NULL DEFAULT '';
ALTER TABLE grimoire ADD COLUMN IF NOT EXISTS graph_capability text NOT NULL DEFAULT 'unavailable'
    CHECK (graph_capability IN ('unavailable', 'semantic_relations', 'relations_declared_empty'));
ALTER TABLE grimoire ADD COLUMN IF NOT EXISTS graph_receipt_id text;

CREATE TABLE IF NOT EXISTS knowledge_graph_node (
    grimoire_id int NOT NULL REFERENCES grimoire(grimoire_id) ON DELETE CASCADE,
    knowledge_id int NOT NULL REFERENCES knowledge(knowledge_id) ON DELETE CASCADE,
    stable_knowledge_id text NOT NULL,
    graph_role text NOT NULL
        CHECK (graph_role IN ('backbone', 'support', 'assessment', 'fragment', 'crosslink')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (grimoire_id, stable_knowledge_id),
    UNIQUE (grimoire_id, knowledge_id)
);

CREATE TABLE IF NOT EXISTS knowledge_graph_edge (
    grimoire_id int NOT NULL REFERENCES grimoire(grimoire_id) ON DELETE CASCADE,
    source_knowledge_id int NOT NULL,
    target_knowledge_id int NOT NULL,
    relation_type text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (grimoire_id, source_knowledge_id, target_knowledge_id, relation_type),
    FOREIGN KEY (grimoire_id, source_knowledge_id)
        REFERENCES knowledge_graph_node(grimoire_id, knowledge_id) ON DELETE CASCADE,
    FOREIGN KEY (grimoire_id, target_knowledge_id)
        REFERENCES knowledge_graph_node(grimoire_id, knowledge_id) ON DELETE CASCADE,
    CHECK (source_knowledge_id <> target_knowledge_id),
    CHECK (relation_type ~ '^[a-z][a-z0-9_.:-]*$')
);

CREATE TABLE IF NOT EXISTS knowledge_graph_receipt (
    receipt_id text NOT NULL,
    grimoire_id int NOT NULL REFERENCES grimoire(grimoire_id) ON DELETE CASCADE,
    book_source_key text NOT NULL,
    contract_version int NOT NULL CHECK (contract_version > 0),
    graph_revision text NOT NULL,
    sidecar_digest text NOT NULL,
    capability text NOT NULL
        CHECK (capability IN ('semantic_relations', 'relations_declared_empty')),
    node_count int NOT NULL CHECK (node_count >= 0),
    relation_count int NOT NULL CHECK (relation_count >= 0),
    diagnostics jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(diagnostics) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (grimoire_id, receipt_id)
);

CREATE INDEX IF NOT EXISTS knowledge_graph_edge_source_idx
    ON knowledge_graph_edge (grimoire_id, source_knowledge_id, relation_type, target_knowledge_id);
CREATE INDEX IF NOT EXISTS knowledge_graph_edge_target_idx
    ON knowledge_graph_edge (grimoire_id, target_knowledge_id, relation_type, source_knowledge_id);
CREATE INDEX IF NOT EXISTS knowledge_graph_receipt_book_idx
    ON knowledge_graph_receipt (grimoire_id, created_at DESC);
CREATE INDEX IF NOT EXISTS section_book_parent_idx
    ON section (grimoire_id, parent_section, section_id);
