-- A2 Conta & Perfil: profile extras + per-user preferences.
-- prefs is an opaque per-user JSON blob (read/written whole by the
-- self-service /v1/account routes — never queried across users, unlike the
-- audit payloads, so a JSON column beats a table here). Portable SQL.

ALTER TABLE users ADD COLUMN job_title TEXT;
ALTER TABLE users ADD COLUMN avatar_color TEXT;
ALTER TABLE users ADD COLUMN prefs TEXT;
