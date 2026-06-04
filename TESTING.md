# Guia de Testes

## Executando

```bash
# Suíte completa (138 testes)
pytest -q

# Com cobertura
pytest --cov=src

# Por área
pytest tests/unit/test_metrics.py -v          # engine de métricas
pytest tests/unit/test_db.py -v               # backend SQLite + migrations
pytest tests/unit/test_orders.py -v           # bridge HITL (OrderStore)
pytest tests/unit/test_agent_registry.py -v   # cycles_today cross-process
pytest tests/api/test_api.py -v               # API /v1 (FastAPI TestClient)
pytest tests/integration/test_trading_flow.py -v   # pipeline strategy→risk→HITL→execução
```

## Estrutura

```
tests/
├── unit/            # métricas, db, orders, agent_registry, alerts, guardrails,
│                    # agents, exchange_dry_run, orchestrator_loop, ledger_durability
├── api/             # test_api.py — endpoints /v1 via FastAPI TestClient
├── integration/     # trading_flow, agent_integration, consensus, unified_orchestration, security_sandbox
└── emergent/        # comportamento emergente
```

## Notas

- **`EXCHANGE_DRY_RUN`**: testes que instanciam o `ExchangeClient` setam a env (zero rede). O gate enxuto de CI (`phase-validation.yml`) **não** instala `ccxt`, então testes que dependem dele (ex.: `test_orchestrator_loop`, `test_trading_flow`) rodam na CI completa (`python-ci.yml`).
- **SQLite/ledger**: testes usam `tmp_path` (db/jsonl temporários) — nada escreve no repositório.
- **Lint**: `ruff check .` é gate bloqueante na CI (correctness set E4/E7/E9/F).

## CI

| Workflow | O que roda |
|---|---|
| `python-ci.yml` | deps completas + `ruff check .` + `pytest` (com cobertura) + docker build + gitleaks |
| `phase-validation.yml` | gate enxuto e rápido (sem `ccxt`/`langchain`): ruff + suítes-alvo das fases |
