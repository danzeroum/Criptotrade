# Roadmap de Execução v4 — Métricas de domínio & documentação de operação

> Continuação de `roadmap_v3.md`. Fecha a história de observabilidade: além de
> métricas HTTP, expõe **métricas de negócio** no `/metrics` e documenta operação
> & escala no README. Branch: `claude/adoring-curie-wknuzy`. 2026-06-20.

## Itens entregues
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| X1 | **Métricas de domínio no Prometheus** (open positions, trades, P&L, win rate, sharpe, portfolio value) via collector que lê o ledger compartilhado no scrape (cross-process-correto) | ✅ | `src/api/observability.py` (`DomainMetricsCollector`); `tests/api/test_observability.py` |
| X2 | Seção **"Observabilidade & Escala"** no README (probes, /metrics, logs, Redis, ADR-005) | ✅ | `README.md` |

## Por que cross-process via collector
O loop do orchestrator roda em **outro processo** que o API. Contadores Prometheus
locais ao processo do API não enxergariam o que o loop faz. O collector lê o
**estado compartilhado** (ledger/DB) no momento do scrape → métricas corretas
independentemente de qual processo gerou o evento.

## Status do arco de produção (v1→v4)
- v1: correção & verdade (IA real, order-routing, persistência, gate de saldo, trades/closed).
- v2: Docker completo + observabilidade base + rate-limit Redis-ready + ADR de escala.
- v3: logs JSON, request-id, heartbeat do loop, fix do `.env`.
- v4: métricas de domínio + docs de operação.

**O arco autônomo de "app de produção, em Docker, pronto para escalar" está
completo.** O que resta exige **infra/decisão do dono** (Postgres, Redis ativo,
multi-réplica, LLM, ir a real) ou **gatilho do ADR-005** — documentado em
`docs/pendencia.v1.md`, `docs/pendencia.v2.md` e `docs/adr/005-scaling-path.md`.
