# Roadmap de Execução v1 — Remediação Criptotrade

> **Tracker vivo** da execução do plano combinado (minha análise + auditoria do
> 2º analista). Atualizado conforme as tarefas são concluídas.
> Início: 2026-06-20 · Branch: `claude/adoring-curie-wknuzy`.
>
> Legenda: ✅ feito · 🔄 em andamento · ⏭️ adiado (com motivo) · ❌ fora de escopo
> · ⛔ bloqueado (ver `docs/pendencia.v1.md`)

## Decisões de escopo do dono (já tomadas)
1. **Camada de IA → integrar LLM de verdade** (default OFF, fail-safe).
2. **Escopo → single-operator** (RBAC/multi-tenant fora).
3. **Dados de mercado → habilitar "preço real + execução paper"** de 1ª classe.

---

## Sprint 0 — Integridade & Verdade
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| I1 | Integrar LLM real (StrategyAgent CoT + RiskAgent Reflection), fail-safe, OFF por padrão | ✅ | `src/core/llm_client.py`; `tests/unit/test_llm_and_routing.py` |
| I2 | `ORDER_ROUTING` desacopla execução de fonte de dados (corrige CT-001) | ✅ | `exchange_client.py`; testes de routing |
| I3 | Fim do fallback silencioso (`stub_used` + alerta `data_fallback`) (CT-005) | ✅ | `strategy_agent.py`, `squad_orchestrator.py`, banner no dashboard |
| I4 | Consolidar docs (README/TESTING/.env.example/dual-autonomy) | ✅ | README env table + nota dual-autonomy; `.env.example`; contagem de testes corrigida (383) |

## Sprint 1 — Correção operacional
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| O1 | Persistir posições abertas + reload no restart (CT-002) | ✅ | `position_store.py`, `migrations/004`, `reload_open_positions` |
| O2 | Gate de saldo pré-trade (CT-003) | ✅ | `risk_agent.py` + `squad_orchestrator._available_capital` |
| O3 | Persistir circuit breaker (CT-004) | ✅ | `CircuitBreaker` persistence + reload |
| O4 | Respeitar `MAX_POSITION_SIZE_PCT`/`STOP_LOSS_PCT`/`MAX_DAILY_LOSS_PCT` do env (CT-013) | ✅ | `guardrails.py`, `risk_agent.py` |
| O5 | Guardrail de condições de mercado não-silencioso | ✅ | StrategyAgent **já envia** `market_context` → efetivo no caminho vivo; o no-op só ocorre em submissões diretas via API (documentado; hardening opcional como backlog) |

## Sprint 2 — Histórico & observabilidade
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| H1 | `GET /v1/trades/closed` + tela de histórico no dashboard (CT-006) | ✅ | `src/api/routes/trades.py`, `ClosedTradeOut`, `tests/api/test_trades.py`, seção no dashboard |

## Sprint 3 — Dívida técnica & qualidade
| ID | Item | Status | Evidência |
|----|------|--------|-----------|
| D1 | `init_db` transacional (CT-010) | ✅ | `db.py` (`_split_sql_statements`, statement-by-statement) |
| D2 | Ratchet de cobertura (66 → 68; alvo 70/80) (CT-011) | ✅ | `pyproject.toml` gate 68; cobertura real ~70.7% |
| D3 | Isolar 9 agentes stub (CT-009) | ⏭️ | **reavaliado**: o 501 de stubs é feature de honestidade testada (`/v1/agents`); isolar removeria isso. Mantido como exposição intencional |
| D4 | `progressive_autonomy.py`: ligar ou remover | ⏭️ | **não é código morto** — usado por `unified_orchestrator` (com testes). Documentado o modelo dual no README; reconciliação adiada |

## Backlog / enhancements
| ID | Item | Status | Nota |
|----|------|--------|------|
| B1 (CT-012) | WebSocket preços live | ⛔ | Depende de ir a `ORDER_ROUTING=live`+rede+exchange real. Ver `docs/pendencia.v1.md` |
| B2 (CT-016) | Rate-limit persistido (multi-worker) | ❌ | Fora de escopo (single-operator, 1 worker) |
| B3 (CT-014) | Ampliar base prices sintéticos (top coins) | ✅ | `synthetic_market._DEFAULT_BASES` (+10 pares) |
| B4 (CT-015) | HSTS 1 ano app-level | ❌ | **declinado**: `max-age=300` no app é intencional (evita fixar HTTPS em localhost); o nginx prod já faz 1 ano |
| CT-017 | Banner "dados sintéticos" no dashboard | ✅ | banner topo + alerta `data_fallback` |
| CT-007 | RBAC/JWT | ❌ | fora de escopo (single-operator) |
| CT-008 | Migrar XES → tabela | ⏭️ | deferido por ADR-003 (volume baixo) |

---

## Status final desta v1
**Núcleo executado (Sprint 0–3).** 383 testes verdes, ruff limpo, cobertura ~70.7%
(gate 68). Itens fora de escopo/adiados documentados acima e em `docs/pendencia.v1.md`.

## Log de execução (commits)
- `47e0ea6` Sprint 0: LLM + ORDER_ROUTING + env risk limits + stub alert.
- `<commit 2>` Sprint 1: persistência de posições/breaker + gate de saldo.
- `<commit 3>` Sprint 2/3 + docs: `/v1/trades/closed` + dashboard, init_db transacional,
  cobertura 68, base prices, banner, README/.env/TESTING, snapshot OpenAPI + types.

## Novos gaps descobertos durante a execução
- **CT-001 do analista tinha premissa incorreta** (flags já separadas; ordem real era
  dead code). Resolvido como exposição de `ORDER_ROUTING` + correção de docs.
- **`progressive_autonomy` não era dead code** (usado por `unified_orchestrator`).
  Tratado como documentação do modelo dual (D4).
