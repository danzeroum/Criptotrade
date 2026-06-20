# Roadmap de Execução v3 — Observabilidade & Operabilidade de produção

> Continuação de `roadmap_v2.md`. Foco: tornar o app **operável e rastreável em
> produção/escala** (logs estruturados, correlação de requests, liveness do loop).
> Branch: `claude/adoring-curie-wknuzy`. Início: 2026-06-20.
>
> Legenda: ✅ feito · ⏭️ adiado (motivo) · ⛔ bloqueado (dono)

## Itens entregues
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| W1 | **Logs estruturados JSON** opt-in (`LOG_FORMAT=json`, lazy import, fallback texto) | ✅ | `src/core/config.py` (`_build_formatter`); `tests/unit/test_logging_format.py` |
| W2 | **Correlação por Request-ID** (`X-Request-ID` propagado + no log via contextvar/filter) | ✅ | `src/api/request_id.py`, `src/core/request_context.py`; `tests/api/test_request_id.py` |
| W3 | **Heartbeat + healthcheck do orchestrator** (loop sem HTTP fica observável) | ✅ | `src/orchestration/heartbeat.py`, `scripts/healthcheck_loop.py`, healthcheck no compose; `tests/unit/test_heartbeat.py` |
| W4 | **Bug latente corrigido:** `Settings` agora ignora chaves extras do `.env` | ✅ | `config.py` (`extra="ignore"`) — `cp .env.example .env` não derruba mais o startup |
| W5 | Ratchet de cobertura 70 → 72 | ✅ | `pyproject.toml` (real ~72.8%) |

## Por que isso importa para escala
- **Logs JSON** → agregação/consulta (Loki/ELK/Datadog) quando há muitas réplicas.
- **Request-ID** → rastrear uma requisição através de múltiplas réplicas e dos logs.
- **Heartbeat** → o compose/k8s reinicia o loop travado; base para futura HA (ADR-005).

## Adiado (com motivo)
| Item | Motivo |
|------|--------|
| Backend Postgres / leader election | gatilhos do ADR-005 não atingidos; rewrite grande sem 2º host para validar |
| Ativar Redis / multi-réplica / LLM / live | dependem de infra/credencial/decisão do dono (`docs/pendencia.v2.md`) |
| Métricas de domínio no Prometheus (trades/ordens) | candidato a v4; HTTP metrics + heartbeat já cobrem o essencial |

## Status final v3
Observabilidade e operabilidade de produção entregues e testadas; **404 testes
verdes**, ruff limpo, cobertura ~72.8% (gate 72). O app está honesto, observável,
containerizado, rastreável e com caminho de escala explícito.
