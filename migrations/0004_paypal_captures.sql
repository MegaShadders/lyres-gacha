BEGIN TRANSACTION;
PRAGMA user_version = 4;

CREATE TABLE paypal_captures (
    capture_id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    product_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

COMMIT;
