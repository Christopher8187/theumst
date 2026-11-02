-- Let one book image belong to several knowledge objects, as when supporting objects restate their theorem's figure.
-- book_image.knowledge_id keeps the first object showing the image; uploads after this migration list every object here.
CREATE TABLE IF NOT EXISTS book_image_knowledge (
    book_image_id bigint NOT NULL REFERENCES book_image(book_image_id) ON DELETE CASCADE,
    knowledge_id int NOT NULL REFERENCES knowledge(knowledge_id) ON DELETE CASCADE,
    PRIMARY KEY (book_image_id, knowledge_id)
);
CREATE INDEX IF NOT EXISTS book_image_knowledge_object_idx
    ON book_image_knowledge (knowledge_id, book_image_id);
