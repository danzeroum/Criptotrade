-- A1 Authentication: users, server-side sessions, password resets.
-- Portable SQL (TEXT uuid PKs, INTEGER 0/1 booleans, TEXT ISO-8601 timestamps)
-- so the same DDL can seed migrations/postgres/ later.

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    name            TEXT,
    password_hash   TEXT,
    role            TEXT NOT NULL DEFAULT 'admin',
    status          TEXT NOT NULL DEFAULT 'active',
    totp_secret_enc TEXT,
    totp_enabled    INTEGER NOT NULL DEFAULT 0,
    backup_codes    TEXT,
    created_at      TEXT NOT NULL,
    last_login_at   TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id                  TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(id),
    token_hash          TEXT NOT NULL UNIQUE,
    refresh_hash        TEXT UNIQUE,
    family_id           TEXT NOT NULL,
    remember            INTEGER NOT NULL DEFAULT 0,
    ip                  TEXT,
    user_agent          TEXT,
    created_at          TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL,
    idle_expires_at     TEXT NOT NULL,
    absolute_expires_at TEXT NOT NULL,
    revoked_at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_family ON sessions(family_id);

CREATE TABLE IF NOT EXISTS password_resets (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at    TEXT
);
