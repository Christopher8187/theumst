-- Link book images to knowledge objects, one row per image, object and kind of link:
-- 'figure' when the object shows the image, as supporting objects restating their theorem's figure do;
-- 'page' when the image is a scan of a page the object appeared on.
-- book_image.knowledge_id keeps a figure's first object; uploads after this migration list every link here.
CREATE TABLE IF NOT EXISTS book_image_knowledge (
    book_image_id bigint NOT NULL REFERENCES book_image(book_image_id) ON DELETE CASCADE,
    knowledge_id int NOT NULL REFERENCES knowledge(knowledge_id) ON DELETE CASCADE,
    link_type text NOT NULL CHECK (link_type IN ('figure', 'page')),
    PRIMARY KEY (book_image_id, knowledge_id, link_type)
);
CREATE INDEX IF NOT EXISTS book_image_knowledge_object_idx
    ON book_image_knowledge (knowledge_id, link_type, book_image_id);
