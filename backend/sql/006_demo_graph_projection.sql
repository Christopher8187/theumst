-- Immutable, lazy Web Demo graph projections derived from canonical book order.

CREATE TABLE IF NOT EXISTS demo_graph_projection (
    grimoire_id int NOT NULL REFERENCES grimoire(grimoire_id) ON DELETE CASCADE,
    book_revision text NOT NULL,
    projection_revision text NOT NULL,
    algorithm text NOT NULL DEFAULT 'book_order_v1'
        CHECK (algorithm = 'book_order_v1'),
    positions jsonb NOT NULL CHECK (jsonb_typeof(positions) = 'array'),
    nodes jsonb NOT NULL CHECK (jsonb_typeof(nodes) = 'array'),
    edges jsonb NOT NULL CHECK (jsonb_typeof(edges) = 'array'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (grimoire_id, book_revision),
    UNIQUE (grimoire_id, projection_revision)
);

CREATE INDEX IF NOT EXISTS demo_graph_projection_created_idx
    ON demo_graph_projection (grimoire_id, created_at DESC);
