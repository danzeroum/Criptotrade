-- A3 RBAC: e-mail invites (the only account-creation path besides bootstrap).
-- Portable SQL, same conventions as 005_auth.sql.

CREATE TABLE IF NOT EXISTS invites (
    id         TEXT PRIMARY KEY,
    email      TEXT NOT NULL,
    role       TEXT NOT NULL,
    token_hash TEXT UNIQUE,
    invited_by TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    accepted_at TEXT,
    revoked_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_invites_email ON invites(email);
