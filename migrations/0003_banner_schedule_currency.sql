BEGIN TRANSACTION;
PRAGMA user_version = 3;

ALTER TABLE banners ADD COLUMN starts_at TEXT;
ALTER TABLE banners ADD COLUMN ends_at TEXT;
ALTER TABLE banners ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;
ALTER TABLE banners ADD COLUMN currency_id INTEGER NOT NULL DEFAULT 1;

UPDATE banners SET currency_id = 1 WHERE id = 1;
UPDATE banners SET currency_id = 2 WHERE id = 2;
UPDATE banners SET currency_id = 2 WHERE id > 2;

UPDATE banners SET sort_order = id * 10 WHERE id IS NOT NULL;

COMMIT;
