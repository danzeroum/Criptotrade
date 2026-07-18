-- A5 Conexões de Exchange & Chaves da Plataforma.
-- exchange_connections.config_enc: JSON {api_key, api_secret} cifrado com o
-- Fernet do AUTH_SECRET_KEY (contrato do 6b). No máximo UMA conexão ativa.
-- platform_api_keys: hash-only para autenticação; key_prefix é só display
-- (nota 3 da revisão). Portable SQL.

CREATE TABLE IF NOT EXISTS exchange_connections (
    id               TEXT PRIMARY KEY,
    exchange_id      TEXT NOT NULL,           -- ccxt id: binance, kraken, ...
    label            TEXT NOT NULL,
    config_enc       TEXT NOT NULL,           -- Fernet JSON {api_key, api_secret}
    scope            TEXT NOT NULL DEFAULT 'read',   -- read | trade
    testnet          INTEGER NOT NULL DEFAULT 1,
    is_active        INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    last_test_at     TEXT,
    last_test_ok     INTEGER,
    last_test_detail TEXT,                    -- JSON: permissões detectadas (mascarado)
    revoked_at       TEXT
);

CREATE TABLE IF NOT EXISTS platform_api_keys (
    id           TEXT PRIMARY KEY,
    label        TEXT NOT NULL,
    key_prefix   TEXT NOT NULL,               -- ex.: 'ctk_a1b2c3d4' (display)
    key_hash     TEXT NOT NULL UNIQUE,        -- sha256 do token completo
    scope        TEXT NOT NULL DEFAULT 'visualizador',  -- papel da matriz A3
    created_by   TEXT,
    created_at   TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at   TEXT
);
