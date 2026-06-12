-- Backtest job persistence (P2-1)
-- Replaces the in-memory _jobs dict in src/api/routes/backtest.py so jobs
-- survive API restarts and are visible across processes.

CREATE TABLE IF NOT EXISTS backtest_jobs (
    id            TEXT PRIMARY KEY,
    status        TEXT NOT NULL CHECK(status IN ('running', 'done', 'error')),
    config_json   TEXT,
    result_json   TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL,
    completed_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtest_jobs_status     ON backtest_jobs(status);
CREATE INDEX IF NOT EXISTS idx_backtest_jobs_created_at ON backtest_jobs(created_at);
