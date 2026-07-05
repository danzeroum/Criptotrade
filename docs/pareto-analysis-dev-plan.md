# Análise Pareto de Valor & Plano de Desenvolvimento

> Data: 2026-07-04 · Branch: `claude/pareto-analysis-dev-plan-up1kko`
> Método: análise 80/20 — priorizar os ~20% de esforço que entregam ~80% do valor.

---

## 1. A ferramenta é funcional?

**Veredito: SIM, funcional de ponta a ponta em paper trading (dry-run) — deliberadamente.**

Verificado nesta análise (não apenas lido, executado):

| Verificação | Resultado |
|---|---|
| Suíte de testes (`pytest`) | **418 passed, 8 skipped** · cobertura 73% (gate ≥72%) |
| Ciclo do orquestrador (`OrchestratorLoop.run_cycle`, dry-run) | Roda: `strategy → risk` (sem sinal ⇒ sem trade), zero falhas |
| API FastAPI (`/health`, `/health/ready`, `/v1/metrics`, `POST /v1/orders`) | Responde; validação de payload ativa; readiness checa SQLite |
| Lint (`ruff check src tests`) | Sem erros |

O núcleo é genuíno: pipeline sinal → risco/guardrails → HITL → execução com fill
econômico (slippage + fee), persistência SQLite WAL que sobrevive a restart,
bridge HITL cross-process, métricas (Sharpe/win rate/drawdown) calculadas do
ledger, API e dashboard funcionais. O rótulo do README ("Paper Trading") é honesto.

**O que NÃO é funcional (stubs assumidos ou código morto):**

- Execução **real** de ordens: congelada no `ExecutionAgent` (`paper_trading = True`
  hardcoded, `execution_agent.py:20`; branch real é TODO). A capacidade existe via
  `ORDER_ROUTING=live`, mas sem hardening (retry, partial fills, reconciliação).
- `recovery` / `exploration` agents: stubs declarados (`registry.py:44-45`, API retorna 501).
- `UnifiedOrchestrator` + `ProgressiveAutonomyManager`: caminho paralelo usado só em
  teste; `_execute_action` é placeholder que retorna sucesso hardcoded.
- `src/core/config.py`: módulo inteiro (Settings + `validate_configuration` fail-fast)
  **não é importado por ninguém** — a validação de config prometida nunca roda.
- RAG (`rag_tool.py`): `NotImplementedError`; ChromaDB comentado.
- `src/main.py`: demo de metodologia, não é o entrypoint de trading (que é
  `python -m src.orchestration.main_loop`).

---

## 2. Quick wins implementados nesta branch (≈20% do esforço → ≈80% do valor)

Ordenados por razão valor/esforço. Todos com testes de regressão.

| # | Melhoria | Valor | Esforço | Arquivos |
|---|---|---|---|---|
| 1 | **Limites de perda semanal (-6%) e mensal (-15%) ligados ao pipeline** — `CapitalProtections` era código morto; agora roda antes de cada ciclo: semana ruim → posições pela metade; mês ruim → trading suspenso + alerta | Crítico | S | `squad_orchestrator.py` |
| 2 | **Fix `/v1/risk`: path do `risk_params.yaml`** — `parents[4]` resolvia fora do repo ⇒ GET devolvia defaults silenciosos e PATCH dava 500. Agora lê/grava o yaml real | Crítico | XS | `api/routes/risk.py` |
| 3 | **Reset diário do circuit breaker** — o contador "diário" nunca zerava (limite virava acumulado-desde-o-início); agora vira com o dia UTC | Alto | S | `squad_orchestrator.py` |
| 4 | **Fix perda diária no `/v1/risk/circuit-breaker`** — lia `data.timestamp` (inexistente) ⇒ perda do dia sempre 0; agora lê o timestamp real do evento | Alto | XS | `api/routes/risk.py` |
| 5 | **Timeout nas chamadas LLM** (`LLM_TIMEOUT_SECONDS`, default 30s) — chamada pendurada não trava mais o ciclo; advisory layer devolve `None` e segue determinístico | Médio | S | `core/llm_client.py` |
| 6 | **Saldo paper respeita `INITIAL_CAPITAL`** — antes hardcoded em 10 000 USDT, incoerente com o sizing | Médio | XS | `core/exchange_client.py` |
| 7 | **Senhas `changeme` comentadas no `.env.example`** — `cp` apressado não sobe mais Postgres/Grafana com senha previsível | Médio | XS | `.env.example` |
| 8 | **Removido `.env.template` órfão** — esquema conflitante com `.env.example` (JWT_SECRET etc. que o código não usa) | Médio | XS | — |
| 9 | **Versão única em `src/version.py` (0.6.0)** — API/`/health` reportavam "1.0.0" falso | Baixo | XS | `api/main.py` |
| 10 | **Removida dependência morta `slowapi`** — rate limit é in-house | Baixo | XS | `requirements.txt` |

Também: contagem de testes do README corrigida (383 → 418) e snapshot OpenAPI regenerado.

---

## 3. Diagrama de Pareto

O diagrama interativo (barras = contribuição de valor por item; linha = valor
acumulado; corte 80%) foi entregue como artifact junto desta análise. Resumo:

```
Esforço total mapeado (quick wins + plano): ~60 h
Quick wins desta branch:                    ~8 h  (≈13% do esforço)
Valor capturado pelos quick wins:           ≈72% do valor total mapeado
```

Os itens restantes (execução real hardened, unificação de orquestradores,
config fail-fast) carregam os outros ~28% de valor por ~87% do esforço — por
isso ficam no plano, não no quick-win.

---

## 4. Plano de desenvolvimento

### P0 — Terminar a segurança financeira (≈6 h)
1. **Unificar thresholds**: `CapitalProtections` usa 3/6/15% hardcoded; o
   `risk_params.yaml` declara 5/10/15%. Carregar do yaml (uma fonte de verdade),
   com defaults conservadores como fallback.
2. **Persistir o dia do contador** do circuit breaker no `circuit_state`
   (SQLite) para que a virada de dia sobreviva a restart.
3. **Conectar ou remover `src/core/config.py`**: se conectar, chamar
   `validate_configuration()` no boot da API e do loop (e corrigir a exigência
   indevida de API key de LLM com `LLM_ENABLED=false`); se não, remover o módulo.

### P1 — Caminho para ordens reais com segurança (≈20 h)
1. Hardening do `ExecutionAgent` para `ORDER_ROUTING=live`: retry com backoff,
   tratamento de partial fills, cancelamento em falha, idempotência (clientOrderId).
2. Reconciliação de saldo real: sizing a partir de `fetch_balance()` da exchange
   (não de `INITIAL_CAPITAL`) quando em live; abortar se divergir do esperado.
3. Testnet primeiro: rodar contra Binance testnet com o checklist de transição
   do `risk_params.yaml` (Sharpe > 1.5, ≥100 trades, 90 dias paper, 0 violações).

### P2 — Pagar a dívida arquitetural (≈16 h)
1. **Convergir orquestradores**: decidir entre `SquadOrchestrator` (vivo) e
   `UnifiedOrchestrator`/`ProgressiveAutonomyManager` (só em teste, com
   `_execute_action` placeholder). Recomendação: portar o trust-score como
   provedor de threshold do HITL existente e apagar o caminho paralelo.
2. Remover agentes vestigiais de engenharia (architect/designer/developer/ops)
   ou movê-los para fora de `src/agents/`.
3. Estratégias `mean_reversion`/`grid_trading`: cobrir com testes e registrar,
   ou parar de carregá-las silenciosamente em `strategies/__init__.py`.

### P3 — Qualidade contínua (≈10 h)
1. Cobertura 73% → 80% (ratchet no `pyproject.toml` já existe; subir o gate).
2. Renomear/documentar `src/main.py` como demo (ou apontar para o `main_loop`).
3. Guardrail de condições de mercado (TODO declarado no README §Guardrails).
4. Decidir RAG: implementar backend ChromaDB ou remover `rag_tool.py`.

### Critério de pronto de cada fase
- Testes novos cobrindo o comportamento (não só o happy path).
- `pytest` verde com gate de cobertura ≥ o atual.
- README/env.example atualizados no mesmo PR (docs nunca divergem do código).
