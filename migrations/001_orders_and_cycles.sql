-- Phase 5a — cross-process state shared between the API and the loop (SQLite/WAL).
-- See ADR-001 and docs: this is the SQLite bridge. Only the two datasets that
-- need cross-process semantics live here; XES events/alerts stay in JSONL for now.

-- Table 1: HITL bridge. Lifecycle pending -> approved -> filled (API decides,
-- loop executes), or pending -> rejected/cancelled.
CREATE TABLE IF NOT EXISTS orders (
    id                TEXT PRIMARY KEY,            -- ord_xxxx
    pair              TEXT NOT NULL,
    side              TEXT NOT NULL CHECK(side IN ('buy','sell')),
    quantity          REAL NOT NULL CHECK(quantity > 0),
    price             REAL NOT NULL CHECK(price > 0),
    strategy          TEXT,
    agent_id          TEXT,
    confidence        REAL,
    reason            TEXT,
    critical          INTEGER NOT NULL DEFAULT 0,  -- bool (0/1)
    position_size_pct REAL,
    stop_loss         REAL,
    take_profit       REAL,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK(status IN ('pending','approved','rejected','cancelled','filled')),
    operator_note     TEXT,
    operator_id       TEXT,
    auto_approved     INTEGER NOT NULL DEFAULT 0,  -- bool (0/1)
    created_at        TEXT NOT NULL,               -- ISO-8601 UTC
    resolved_at       TEXT,
    filled_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

-- Table 2: append-only cycle events. The API serves cycles_today via an indexed
-- SELECT COUNT (no cross-process counter, no UPDATE contention).
CREATE TABLE IF NOT EXISTS cycle_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id  TEXT NOT NULL,
    cycled_at TEXT NOT NULL                        -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_cycle_agent_day ON cycle_events(agent_id, cycled_at);
