# Roadmap de Execução v6 — Backend PostgreSQL (escala horizontal real)

> Decisão do dono: **"Backend PostgreSQL agora"**. Implementa Postgres como
> backend **opcional** do estado compartilhado, mantendo SQLite como padrão.
> **Testado contra um Postgres 16 real.** Branch: `claude/adoring-curie-wknuzy`. 2026-06-21.

## Itens entregues
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| Z1 | Camada `db.py` dual-backend (SQLite default · Postgres via `DATABASE_URL`) | ✅ | `src/core/db.py`: `is_postgres`, `connection`, `_PgConn`, `_Row`, `upsert`, `autoincrement_pk` |
| Z2 | Tradução transparente: `?`→`%s`, rows com `[0]` **e** `["col"]`, `dict(row)` | ✅ | `_PgConn`, `_hybrid_row_factory`, `_Row` |
| Z3 | Upserts backend-aware (`INSERT OR REPLACE/IGNORE` ↔ `ON CONFLICT`) | ✅ | `db.upsert` em `position_store`, `init_db` (schema_migrations) |
| Z4 | Migrations Postgres (`BIGSERIAL`, default `to_char`) | ✅ | `migrations/postgres/001-004.sql`; `init_db` escolhe o dir por backend |
| Z5 | `RETURNING id` no journal (sem `lastrowid` no PG) | ✅ | `src/api/routes/journal.py` |
| Z6 | Teste de integração **real** contra Postgres 16 (gated por `DATABASE_URL`) | ✅ | `tests/integration/test_postgres_backend.py` — 8 testes passando |
| Z7 | `psycopg[binary]` (lazy) + serviço `postgres` no compose (perfil `scale`) | ✅ | `requirements.txt`, `docker-compose.yml` |
| Z8 | Docs: ADR-005, README (`DATABASE_URL`), pendencia | ✅ | — |

## Como ativar
```bash
DATABASE_URL=postgresql://ct:ct@postgres:5432/criptotrade \
POSTGRES_USER=ct POSTGRES_PASSWORD=ct \
  docker compose --profile scale up -d
```
Sem `DATABASE_URL`, tudo roda em SQLite como antes.

## Garantias
- **SQLite segue padrão e 100% testado** (406 testes, inalterados). O backend PG é
  exercitado por um teste de integração dedicado (8 testes) contra Postgres real,
  **pulado quando não há `DATABASE_URL`** (ex.: CI).
- Linhas exclusivas de PG marcadas `# pragma: no cover` (cobertas pelo teste
  gated), mantendo o gate de cobertura honesto para o núcleo SQLite.

## Resta (gated por ADR-005 / decisão do dono)
- **Leader election** do orchestrator (HA real com loop redundante) — só quando
  "zero downtime do trading" for requisito.
- Provisionar Postgres gerenciado + deploy multi-réplica em produção.
