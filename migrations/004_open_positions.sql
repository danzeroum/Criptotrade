-- 004: persist the paper position book + circuit-breaker state across restarts.
--
-- Without this the orchestrator loop's in-memory state is lost on restart,
-- leaving "zombie" open positions that are never closed at stop/TP (CT-002) and
-- a circuit breaker that forgets a loss streak (CT-004). The PositionStore also
-- creates these tables defensively (CREATE TABLE IF NOT EXISTS), so this
-- migration mainly documents the schema and provisions the production db.

CREATE TABLE IF NOT EXISTS open_positions (
    order_id    TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    entry_price REAL NOT NULL,
    quantity    REAL NOT NULL,
    stop_loss   REAL,
    take_profit REAL,
    opened_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_open_positions_symbol ON open_positions(symbol);

CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    tripped_at         REAL,
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    daily_loss_pct     REAL NOT NULL DEFAULT 0.0
);
