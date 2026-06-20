# ADR-005: Caminho de Escalabilidade (single-host → horizontal)

## Status
✅ Aceita (2026-06-20)

## Contexto
Hoje o sistema roda **inteiramente em Docker num único host**. O estado
cross-process (API + loop) vive em **SQLite WAL** (ADR-003). Isso é simples e
correto para 1 host e para o MVP, mas tem limites conhecidos para crescer:

- WAL **não é válido sobre NFS / múltiplos hosts** (ADR-001).
- O rate limit era **por-processo** (não compartilhado entre réplicas).
- Faltava telemetria padronizada para autoscaling/observabilidade.

O objetivo desta ADR é deixar o app **"pronto para escalar quando crescer"** sem
fazer um rewrite agora.

## Decisão
Manter **SQLite + single-host como padrão** (dev/MVP) e embutir pontos de
extensão para escala horizontal, ativáveis por env/infra:

1. **API stateless → N réplicas atrás de LB.** O nginx já existe no
   `docker-compose.prod.yml`. Nenhum estado vive no processo da API.
2. **Rate limit compartilhado.** `REDIS_URL` ativa o `RedisFixedWindowLimiter`
   (`src/core/ratelimit.py`); default in-memory. Fail-open se o Redis cair.
3. **Observabilidade.** `GET /metrics` (Prometheus) + `GET /health/ready`
   (readiness gating para compose/k8s) + `GET /health` (liveness).
4. **Estado compartilhado → PostgreSQL.** Quando houver >1 host que **escreve**
   estado, migrar a camada única `src/core/db.py` de SQLite para Postgres
   (`sqlalchemy` já é dependência). É o **único** ponto a trocar.
5. **Orchestrator é singleton por design.** Um único loop escreve ledger/posições.
   Para HA, fazer **leader election** (ex.: advisory lock no Postgres) **antes**
   de rodar 2 loops. Nunca rodar 2 loops sobre o mesmo estado.
6. **Fan-out de eventos.** SSE hoje; em escala, broker (Redis pub/sub ou NATS)
   para distribuir alertas a muitos consumidores — futuro.

## Gatilhos de migração
- **→ Redis (rate limit/cache):** assim que houver ≥2 réplicas de API.
- **→ Postgres:** ≥2 hosts escrevendo estado, contenção de WAL, ou necessidade
  de réplica de leitura.
- **→ leader election no loop:** quando "zero downtime do trading" virar requisito.

## Consequências
- **Positivas:** caminho incremental; cada degrau é ativável por env/infra; o
  código já tem os ganchos (rate-limit pluggable, /metrics, /health/ready).
- **Negativas:** o backend Postgres e o leader-election ainda **não** estão
  implementados — são trabalho futuro guiado pelos gatilhos acima
  (ver `docs/pendencia.v2.md`).

## Referências
- ADR-001 (paper trading / WAL não sobre NFS), ADR-003 (persistência SQLite WAL).
- `src/core/ratelimit.py`, `src/api/observability.py`, `docker-compose.yml` (perfil `scale`).
