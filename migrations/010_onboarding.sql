-- A10 Onboarding: single-row SYSTEM status (single-user platform — the wizard
-- configures the system, not personal preferences). Only HUMAN decisions are
-- persisted (skips, manual completes, dismiss, completion stamp); everything
-- else is derived live from the real system state on every GET, so the
-- checklist can never lie. Portable SQL.

CREATE TABLE IF NOT EXISTS onboarding_status (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    skipped          TEXT NOT NULL DEFAULT '[]',   -- JSON array of step ids
    completed_manual TEXT NOT NULL DEFAULT '[]',   -- JSON array of step ids
    dismissed        INTEGER NOT NULL DEFAULT 0,   -- "pular por agora"
    completed_at     TEXT                          -- stamped once; never unset
);
