-- N8² (Fase 11): DB-managed operated pairs — padrão A5 (DB > env).
-- Quando esta tabela tem linhas, operated_pairs() usa elas (∩ allowlist);
-- vazia/ausente → fallback para o env SYMBOLS (retrocompatível).
-- paused (N9) é lido POR CICLO pelo loop (pausar não exige restart; adicionar/
-- remover sim). added_at ordena a exibição.
CREATE TABLE IF NOT EXISTS operated_pairs (
    symbol   TEXT PRIMARY KEY,
    paused   INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL
);
