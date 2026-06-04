# 🤖 Criptotrade — Crypto AI Trading Platform

> **Plataforma de trading automatizado de cripto com agentes de IA, priorizando segurança, gestão de risco e Human-in-the-Loop.**

[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Paper%20Trading-blue)](https://github.com)

---

## 📋 Visão Geral

Sistema de trading automatizado com **agentes de IA especializados** que colaboram para analisar mercados, validar risco e executar ordens de forma auditável — com **aprovação humana (HITL)** e **modo dry-run** por padrão (zero conexão real à exchange).

O ciclo central, vivo e testado:

```
signal (Strategy) → risk + guardrails (Risk) → HITL (auto/manual) → execução → filled
```

Roda **cross-process**: um processo de **API** (FastAPI) e um processo de **loop** (orquestrador contínuo) compartilham estado via **SQLite (WAL)**, permitindo que um operador aprove/rejeite ordens pelo dashboard enquanto o loop opera.

---

## 🏗️ Arquitetura

Dois processos separados (não compartilham lifecycle — um restart da API não para o trading):

```
        ┌──────────────────────┐         ┌──────────────────────────────┐
        │   API (uvicorn)       │         │  Orchestrator loop (process) │
        │  src.api.main:app     │         │  python -m src.orchestration │
        │                       │         │            .main_loop        │
        │  /v1/metrics          │         │                              │
        │  /v1/hitl/config      │         │  OrchestratorLoop            │
        │  /v1/orders  (HITL)   │         │   └─ SquadOrchestrator        │
        │  /v1/agents           │         │       Strategy → Risk →       │
        │  /v1/process/events   │         │       Guardrails → HITL →      │
        │  /v1/alerts (SSE)     │         │       Execution               │
        └──────────┬───────────┘         └──────────────┬───────────────┘
                   │   estado compartilhado (mesmo host/volume)          │
                   ▼                                                     ▼
         ┌───────────────────────────────────────────────────────────────┐
         │  Persistência (LEDGER_DIR)                                     │
         │  • SQLite WAL: orders (bridge HITL), cycle_events (agentes)    │
         │  • JSONL: ledger de auditoria + event log XES (process mining) │
         └───────────────────────────────────────────────────────────────┘
                   ▲
                   │  consome a API via HTTP
         ┌─────────┴──────────┐
         │ Dashboard (Streamlit)│  KPIs · Console HITL · Agentes · Alertas
         └────────────────────┘
```

### Componentes principais

| Componente | Responsabilidade | Onde |
|---|---|---|
| **StrategyAgent / RiskAgent / ExecutionAgent** | Sinal, validação de risco (guardrails), execução paper | `src/agents/` |
| **GuardrailSystem** | Bloqueio per-order (position size, stop loss, risk-reward) | `src/safety/guardrails.py` |
| **SquadOrchestrator** | Pipeline strategy→risk→HITL→execução | `src/orchestration/squad_orchestrator.py` |
| **OrchestratorLoop / main_loop** | Loop contínuo (processo dedicado), emite event log XES | `src/orchestration/orchestrator_loop.py`, `main_loop.py` |
| **OrderStore** | Bridge HITL cross-process (lifecycle `pending→approved→filled`) | `src/hitl/orders.py` |
| **AgentRegistry** | `cycles_today` cross-process (SELECT COUNT) | `src/agents/registry.py` |
| **PortfolioMetricsCalculator** | Sharpe / Win Rate / Drawdown / P&L do ledger | `src/core/metrics.py` |
| **TradingLedger** | Ledger append-only (JSONL) + event log XES | `src/core/ledger.py` |
| **SQLite (WAL)** | Estado cross-process (`orders`, `cycle_events`) | `src/core/db.py`, `migrations/` |
| **API (FastAPI)** | Gateway `/v1` (métricas, HITL, ordens, agentes, alertas) | `src/api/` |
| **Dashboard (Streamlit)** | Console operacional (HITL, KPIs, agentes, alertas) | `src/dashboard/app.py` |

---

## 🚀 Quick Start

### Pré-requisitos
- Python 3.11+
- (Opcional) Docker & Docker Compose
- (Opcional para LLM) `GOOGLE_API_KEY` (Gemini) — o ciclo de trading roda sem isso em dry-run

### Instalação

```bash
git clone https://github.com/danzeroum/Criptotrade.git
cd Criptotrade

cp .env.example .env          # ajuste conforme a tabela de env vars abaixo
pip install -r requirements.txt

pytest -q                     # 138 testes
```

### Rodando (3 processos independentes)

```bash
# 1) API (FastAPI) — docs interativas em http://localhost:8000/v1/docs
uvicorn src.api.main:app --port 8000

# 2) Loop de trading (processo SEPARADO da API) — exige EXCHANGE_DRY_RUN
EXCHANGE_DRY_RUN=true python -m src.orchestration.main_loop

# 3) Dashboard (consome a API)
API_URL=http://localhost:8000 streamlit run src/dashboard/app.py
```

Ou tudo via Docker (`app` = API/dashboard, `orchestrator` = loop):

```bash
docker compose up -d
```

> ⚠️ **`EXCHANGE_DRY_RUN` é obrigatório** (sem default). `true` = dados de mercado sintéticos, **zero rede**; `false` = exchange real (apenas produção, decisão deliberada). Sem a variável, o cliente recusa iniciar.

### Uso programático (dry-run, offline)

```python
import asyncio
from src.orchestration.orchestrator_loop import OrchestratorLoop  # requer EXCHANGE_DRY_RUN=true

loop = OrchestratorLoop.from_env(symbols=["BTC/USDT"])
result = asyncio.run(loop.run_cycle())   # 1 ciclo: strategy → risk → HITL → execução
print(result["ran"])                     # ex.: ['strategy', 'risk', 'execution']
```

---

## ⚙️ Variáveis de ambiente

| Variável | Default | Descrição |
|---|---|---|
| `EXCHANGE_DRY_RUN` | **(obrigatória)** | `true` = sintético/offline · `false` = exchange real (produção) |
| `DRY_RUN_BASE_PRICE` | `50000` | Preço-base do mercado sintético (determinístico) |
| `AUTONOMY_LEVEL` | `2` | Nível HITL 0–3 (threshold de auto-aprovação por valor) |
| `INITIAL_CAPITAL` | `10000` | Capital base (dimensiona quantidade e métricas) |
| `LEDGER_DIR` | `.buildtovalue/ledger` | Diretório do ledger JSONL + `criptotrade.db` (montar volume em prod) |
| `ORCHESTRATOR_INTERVAL_SECONDS` | `60` | Intervalo do loop (validado 10–3600) |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` | — | LLM (Gemini primário; OpenAI backup) |
| `EXCHANGE` / `EXCHANGE_API_KEY` / `EXCHANGE_API_SECRET` / `EXCHANGE_TESTNET` | binance / … | Exchange (só usados quando `EXCHANGE_DRY_RUN=false`) |
| `API_KEYS` | — | API keys do gateway (se vazio, API aberta em dev) |
| `API_URL` / `API_KEY` (dashboard) | `http://localhost:8000` / — | Dashboard → API |

Veja `.env.example` para a lista completa.

---

## 🔒 Segurança & HITL

### Modelo de autonomia (HITL) — níveis 0–3

| Nível | Threshold auto-aprovação | Comportamento |
|---|---|---|
| 0 | $0 | Manual total — toda ordem exige aprovação humana |
| 1 | $500 | Semiautônomo baixo |
| 2 (padrão) | $1.000 | Semiautônomo médio |
| 3 | $5.000 | Semiautônomo alto (alertas críticos ainda requerem humano) |

**Lifecycle de uma ordem** (cross-process via SQLite):
- **Auto** (notional ≤ threshold, não-crítica): `pending → filled` direto.
- **Manual**: `pending → ` (operador aprova na API/dashboard) `→ approved → ` (loop executa) `→ filled`. Sem resposta no prazo (`decision_timeout`, default 300s) → `cancelled` (**fail-closed**).

### Guardrails (per-order, ativos no caminho vivo)
- Position size ≤ 5% do portfólio · Stop loss obrigatório · Risk-reward ≥ 2.5 · (condições de mercado: TODO).
- Rodam no **RiskAgent** (pipeline) e no **OrderStore** (gate antes da auto-aprovação). Violação → `rejected` com motivo + alerta publicado.

### Persistência & auditoria
- **JSONL** (`LEDGER_DIR`): ledger append-only + event log XES (process mining).
- **SQLite WAL** (`LEDGER_DIR/criptotrade.db`): `orders` e `cycle_events` (estado cross-process). Decisão registrada em [ADR-003](docs/adr/003-persistence-sqlite-wal.md).

---

## 🌐 API (`/v1`)

Docs interativas (OpenAPI auto-gerado): **`http://localhost:8000/v1/docs`**.

| Endpoint | Descrição |
|---|---|
| `GET /v1/metrics` | Sharpe, Win Rate, Max Drawdown, P&L, exposição |
| `GET/PATCH /v1/hitl/config` | Nível de autonomia (0–3) |
| `GET /v1/orders` · `POST /v1/orders` · `PATCH /v1/orders/{id}/status` | Lista / submete / aprova-rejeita ordens (HITL) |
| `GET /v1/agents` · `GET /v1/agents/{id}` | Status dos agentes + `cycles_today` (501 para stubs) |
| `GET /v1/process/events` | Event log XES (process mining) |
| `GET /v1/alerts` (SSE) · `GET /v1/alerts/history` | Alertas de guardrail em tempo real / histórico |

---

## 📁 Estrutura do projeto

```
Criptotrade/
├── src/
│   ├── api/                # FastAPI gateway (/v1) — routes, schemas, deps
│   ├── agents/             # strategy, risk, execution, registry, ...
│   ├── core/               # config, ledger (JSONL), db (SQLite), metrics, alerts, exchange_client
│   ├── hitl/               # config (autonomia 0–3), orders (bridge SQLite), progressive_autonomy
│   ├── safety/             # guardrails, security_config
│   ├── orchestration/      # squad_orchestrator, orchestrator_loop, main_loop (entrypoint)
│   ├── strategies/         # DCA otimizado, base_strategy
│   ├── dashboard/          # Streamlit (console operacional)
│   └── ...                 # evaluation, memory, planning, consensus, ...
├── migrations/             # SQL versionado (001_orders_and_cycles.sql)
├── config/                 # constitution.yaml, strategies/risk_params.yaml, prometheus.yml
├── docs/                   # ADRs, validação de planos, UX, tutoriais
├── tests/                  # unit, integration, emergent
├── docker-compose.yml      # serviços: app (API/dashboard), orchestrator (loop), prometheus
└── Dockerfile
```

---

## 🧪 Testes

```bash
pytest -q                                   # suíte completa (138 testes)
pytest tests/unit/test_orders.py -v         # bridge HITL (OrderStore SQLite)
pytest tests/unit/test_db.py -v             # backend SQLite + migrations
pytest tests/integration/test_trading_flow.py -v
```

CI (GitHub Actions): `python-ci.yml` (suíte completa + ruff + docker build + secret-scan) e `phase-validation.yml` (gate enxuto e rápido das fases sem deps pesadas).

---

## 🔄 Roadmap

### ✅ Entregue
- [x] Agentes fundamentais (Strategy, Risk, Execution) + guardrails no caminho vivo
- [x] Engine de métricas (Sharpe / Win Rate / Drawdown) a partir do ledger
- [x] API Gateway `/v1` (FastAPI) + dashboard operacional (Streamlit)
- [x] Paper trading / `EXCHANGE_DRY_RUN` (sintético, zero rede)
- [x] Loop contínuo em processo dedicado (`main_loop`) + event log XES
- [x] Bridge HITL cross-process via SQLite WAL (auto + manual, `approved→filled`)
- [x] `cycles_today` cross-process · ADR-001 (persistência)

### 🔜 Backlog (Fase 5b — janitorial/observabilidade)
- [ ] Tech debts `TODO(5b)` (reset de `_last_order_ref`, `wait_for_decision` com id inexistente, etc.)
- [ ] Pruning de `cycle_events`; migração de XES events → SQLite (fecha ADR-001)
- [ ] Filtrar agentes `not_implemented` no dashboard; paginação em `/v1/orders`

---

## 🤝 Contribuindo

Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`). Abra PRs contra `master`; a CI precisa passar (testes + ruff).

---

## ⚠️ Disclaimer

Software fornecido "como está", sem garantias. Trading de cripto envolve risco substancial de perda. Fase de **paper trading / pesquisa** — não é aconselhamento financeiro. DYOR.

## 📄 Licença

[MIT License](LICENSE).
