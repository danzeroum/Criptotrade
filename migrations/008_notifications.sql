-- A6 Notificações & Canais: delivery channels, event×severity rules,
-- quiet hours and the dispatcher's cursor over alerts.jsonl.
-- config_enc is the channel's config JSON encrypted with the AUTH_SECRET_KEY
-- Fernet (same contract A5 will use for exchange keys). Portable SQL.

CREATE TABLE IF NOT EXISTS notification_channels (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,          -- email | telegram | slack | webhook
    label        TEXT NOT NULL,
    config_enc   TEXT NOT NULL,          -- Fernet-encrypted JSON
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    last_test_at TEXT,
    last_test_ok INTEGER,
    last_error   TEXT
);

CREATE TABLE IF NOT EXISTS notification_rules (
    id           TEXT PRIMARY KEY,
    alert_type   TEXT NOT NULL DEFAULT '*',   -- '*' = any alert type
    min_severity TEXT NOT NULL DEFAULT 'high',
    channel_ids  TEXT NOT NULL,               -- JSON array of channel ids
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);

-- Single-row settings (id fixed at 1).
CREATE TABLE IF NOT EXISTS notification_settings (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    quiet_start      TEXT,                    -- 'HH:MM' (NULL = no quiet hours)
    quiet_end        TEXT,
    quiet_tz         TEXT NOT NULL DEFAULT 'America/Sao_Paulo',
    group_window_min INTEGER NOT NULL DEFAULT 5
);

-- Byte-offset cursor over alerts.jsonl (append-only, so the offset is a valid
-- cursor). Advanced with an OPTIMISTIC update so N workers never double-send.
CREATE TABLE IF NOT EXISTS notifications_cursor (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    pos        INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT
);
