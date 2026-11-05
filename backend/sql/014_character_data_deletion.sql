-- Theumst 0.0.11: a character's save goes with the character.
-- "character".character_data_id references character_data ON DELETE CASCADE,
-- which deletes a character with its save but not a save with its character:
-- deleting a character, or its account through the user cascade, left its
-- character_data row behind. From here deleting a "character" row deletes its
-- character_data row, and saves no character points at are removed.
-- Safe on tables that already hold rows; every statement can run again.

-- After the character row is gone, so the foreign key's cascade from the save
-- back to "character" finds nothing more to delete.
CREATE OR REPLACE FUNCTION delete_character_data()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM character_data WHERE character_data_id = OLD.character_data_id;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS character_delete_character_data ON "character";
CREATE TRIGGER character_delete_character_data
AFTER DELETE ON "character"
FOR EACH ROW EXECUTE FUNCTION delete_character_data();

-- Saves left by characters deleted before the trigger existed.
DELETE FROM character_data d
WHERE NOT EXISTS (
    SELECT 1 FROM "character" c WHERE c.character_data_id = d.character_data_id
);
