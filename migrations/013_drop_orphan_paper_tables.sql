-- Fix (accounting forensics): the paper position book + circuit-breaker state are
-- RUNTIME state the orchestrator persists in the LEDGER db (LEDGER_DIR/trades.db)
-- via PositionStore/CircuitBreaker — every reader (desk, risk, observability) opens
-- `connection(ledger.db_path)`. Migration 004 also provisioned EMPTY copies of these
-- tables in the app db (LEDGER_DIR/criptotrade.db) that nothing reads or writes.
-- Two `open_positions` tables in two files is a forensic trap (a query against the
-- app db reports 0 while 12 lots sit in trades.db). Drop the orphans here; the real
-- tables live in trades.db and are self-created (CREATE TABLE IF NOT EXISTS) by
-- PositionStore. This migration runs only against the app db, so it never touches
-- the live trades.db copies.
DROP TABLE IF EXISTS open_positions;
DROP TABLE IF EXISTS circuit_breaker_state;
