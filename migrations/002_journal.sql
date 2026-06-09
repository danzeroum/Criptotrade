-- Diário Comportamental
-- Registros de trades com contexto emocional e disciplina

CREATE TABLE IF NOT EXISTS journal_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    setup           TEXT    NOT NULL,
    emotion_before  INTEGER NOT NULL CHECK(emotion_before BETWEEN 1 AND 10),
    emotion_after   INTEGER          CHECK(emotion_after  BETWEEN 1 AND 10),
    stop_defined    INTEGER NOT NULL DEFAULT 0,   -- 0=false 1=true
    plan_followed   INTEGER NOT NULL DEFAULT 0,   -- 0=false 1=true
    pnl_pct         REAL,
    note            TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_journal_created ON journal_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_journal_emotion  ON journal_entries(emotion_before);
