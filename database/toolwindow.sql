BEGIN;

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('opened', 'closed')),
    source TEXT CHECK(source IN ('auto', 'manual', '')),
    duration INTEGER NOT NULL
);

CREATE INDEX idx_timestamp ON tickets(timestamp);

CREATE INDEX idx_status ON tickets(status);
