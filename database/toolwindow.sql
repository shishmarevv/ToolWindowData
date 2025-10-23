CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    event TEXT NOT NULL CHECK(event IN ('opened', 'closed')),
    type TEXT CHECK(type IN ('auto', 'manual'))
);

CREATE TABLE IF NOT EXISTS clear (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('auto', 'manual')),
    start INTEGER NOT NULL,
    end INTEGER NOT NULL,
    open_event_id INTEGER NOT NULL,
    close_event_id INTEGER NOT NULL,
    FOREIGN KEY(open_event_id) REFERENCES events(id),
    FOREIGN KEY(close_event_id) REFERENCES events(id)
);

CREATE TABLE IF NOT EXISTS anomaly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NULL,
    timestamp INTEGER NOT NULL,
    counterparty_event_id INTEGER NULL,
    event_id INTEGER NOT NULL,
    detail TEXT NOT NULL CHECK ( detail IN ('missing_close',
                                            'missing_open',
                                            'null_type',
                                            'closed_not_null_type',
                                            'negative_duration',
                                            '>12h_duration') ),
    FOREIGN KEY(counterparty_event_id) REFERENCES events(id),
    FOREIGN KEY(event_id) REFERENCES events(id)
);

CREATE INDEX IF NOT EXISTS idx_event_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_action_timestamp ON events(timestamp, type);
CREATE INDEX IF NOT EXISTS idx_event_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_event ON events(id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_events_dedupe
ON events(user_id, timestamp, event, COALESCE(type, ''));

CREATE INDEX IF NOT EXISTS idx_clear_action_start ON clear(type, start);
CREATE INDEX IF NOT EXISTS idx_clear_start ON clear(start);

CREATE INDEX IF NOT EXISTS idx_anomaly_timestamp ON anomaly(timestamp);
CREATE INDEX IF NOT EXISTS idx_anomaly_detail_timestamp ON anomaly(detail, timestamp);

-- Support per-user ordered scans
CREATE INDEX IF NOT EXISTS idx_events_user_ts_id ON events(user_id, timestamp, id);

-- Ensure idempotency for episodes: each (open_event_id, close_event_id) pair only once
CREATE UNIQUE INDEX IF NOT EXISTS ux_clear_pair ON clear(open_event_id, close_event_id);

-- Ensure idempotency for anomalies with and without counterparty
CREATE UNIQUE INDEX IF NOT EXISTS ux_anomaly_unique_null
ON anomaly(event_id, detail)
WHERE counterparty_event_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_anomaly_unique_counterparty
ON anomaly(event_id, counterparty_event_id, detail)
WHERE counterparty_event_id IS NOT NULL;