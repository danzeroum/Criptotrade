# Roadmap de Execução v2 — App de produção, em Docker e pronto para escalar

> Continuação do `roadmap_v1.md`. Foco: **tudo em Docker agora, pronto para
> escalar quando crescer** (observabilidade, hardening de container, escala
> horizontal). Branch: `claude/adoring-curie-wknuzy`. Início: 2026-06-20.
>
> Legenda: ✅ feito · 🔄 em andamento · ⏭️ adiado (motivo) · ⛔ bloqueado (dono)

## Observabilidade (scale-ready)
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| V1 | `GET /metrics` Prometheus + middleware (req count + latência, labels por rota) | ✅ | `src/api/observability.py`; `tests/api/test_observability.py` |
| V2 | `GET /health/ready` (readiness: checa SQLite) + `/health` liveness | ✅ | `main.py`; testes |
| V3 | Prometheus passa a ter alvo real (`/metrics`) | ✅ | `config/prometheus.yml` já aponta `app:8000` |

## Escala horizontal
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| V4 | Rate limit pluggable: in-memory (default) ou **Redis** (REDIS_URL) | ✅ | `src/core/ratelimit.py`; `tests/unit/test_ratelimit.py` |
| V5 | ADR-005 — caminho single-host → horizontal (Redis, Postgres, leader election) | ✅ | `docs/adr/005-scaling-path.md` |
| V6 | Backend Postgres para estado compartilhado | ⏭️ | gatilho no ADR-005 (>1 host escrevendo). `db.py` é o ponto único; `sqlalchemy` já é dep |
| V7 | Leader election do orchestrator (HA) | ⏭️ | ADR-005; só quando "zero downtime" for requisito |

## Docker (tudo em container)
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| V8 | Serviço `dashboard` (Streamlit) no compose — antes 8501 exposto sem processo | ✅ | `docker-compose.yml` |
| V9 | Healthchecks (app `/health/ready`, prometheus, redis) + `depends_on: service_healthy` | ✅ | `docker-compose.yml` |
| V10 | Perfil `scale` com Redis (`docker compose --profile scale up`) | ✅ | `docker-compose.yml` |
| V11 | `.dockerignore` (contexto menor/sem segredos → builds mais rápidos) | ✅ | `.dockerignore` |
| V12 | Heartbeat/healthcheck do orchestrator (sem HTTP) | ⏭️ | sem endpoint HTTP; `restart: unless-stopped` cobre crash. Futuro: arquivo de heartbeat |

## Qualidade
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| V13 | Ratchet de cobertura 68 → 70 | ✅ | `pyproject.toml` |

---

## Status final v2
Observabilidade + hardening de Docker + prontidão para escala **implementados e
testados**; o caminho para Postgres/leader-election/Redis está documentado
(ADR-005) e ativável por env/infra. Suíte verde, ruff limpo.

## Pendências do dono → `docs/pendencia.v2.md`
Provisionar Redis (+`pip install redis`+`REDIS_URL`) para escala; decisão de
migrar a Postgres; deploy multi-réplica.
