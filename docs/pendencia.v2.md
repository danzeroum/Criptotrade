# Pendências do Dono — v2 (escala & produção)

> Itens que dependem de **decisão ou infra do dono**. O código já está pronto e
> com os ganchos; ativar exige provisionamento. Ver também `docs/pendencia.v1.md`
> e `docs/acaoPendenteDono.md`. Atualizado: 2026-06-20.

## 🟠 Escala horizontal (quando crescer)
- [ ] **Redis para rate limit compartilhado.** Para rodar ≥2 réplicas da API:
  1. `pip install redis` (a lib é opcional; não está em `requirements.txt`).
  2. Definir `REDIS_URL=redis://redis:6379/0` no `.env`.
  3. Subir o perfil de escala: `docker compose --profile scale up -d`.
  Sem isso, o rate limit é per-processo (correto para 1 réplica).

- [ ] **PostgreSQL para estado compartilhado.** Necessário quando houver >1 host
  escrevendo estado (ver gatilhos no ADR-005). Migração concentrada em
  `src/core/db.py` (SQLAlchemy já é dependência). Hoje: SQLite WAL (1 host).

- [ ] **Leader election do orchestrator.** Para HA do loop (rodar réplica passiva
  sem dois loops escrevendo o mesmo estado). Implementar via advisory lock no
  Postgres **depois** da migração acima.

- [ ] **Deploy multi-réplica.** O `docker-compose.prod.yml` (nginx TLS) já existe;
  para múltiplas réplicas da API, escalar o serviço atrás do nginx e ativar Redis.

## ℹ️ Já entregue nesta v2 (sem ação do dono)
- `/metrics` (Prometheus) e `/health/ready` no app; Prometheus já com alvo real.
- Rate limit pluggable (Redis-ready, fail-open).
- `dashboard` Streamlit no compose; healthchecks; perfil `scale`; `.dockerignore`.
- ADR-005 (caminho de escala) documentado.
