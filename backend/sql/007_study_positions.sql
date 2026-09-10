-- Preserve independent Text and Questions positions without changing completion.
ALTER TABLE demo_study_state ADD COLUMN IF NOT EXISTS questions_knowledge_id int
    REFERENCES knowledge(knowledge_id) ON DELETE SET NULL;
