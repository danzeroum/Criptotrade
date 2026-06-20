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

> **Design:** o console React em `docs/design/pages/` é buildado no CI (esbuild) e servido pelo nginx em produção (`docker-compose.prod.yml`) — o `dist/` é gitignored. A UI operacional padrão continua sendo o dashboard Streamlit.

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

pytest -q                     # 383 testes
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

### Produção (TLS + reverse proxy)

O `docker compose up -d` acima é o stack de **dev** (HTTP puro, portas expostas, auth/CORS abertos). Para produção use o arquivo dedicado **`docker-compose.prod.yml`**: nginx termina TLS (Let's Encrypt) e faz proxy reverso pra API — só `80/443` ficam expostos; app, orchestrator e prometheus ficam apenas na rede interna.

```bash
# 1) Segredos (a API recusa iniciar em prod sem isto):
cp .env.prod.example .env
#    edite .env → API_KEYS = valor forte (ex.: openssl rand -hex 32)

# 2) Emitir o certificado (uma vez; exige DNS do domínio apontando pra cá + portas 80/443 abertas):
./deploy/init-letsencrypt.sh

# 3) Subir o stack de produção:
docker compose -f docker-compose.prod.yml up -d
```

> **Não é overlay**: use `-f docker-compose.prod.yml` sozinho (o compose de dev publica `8000/8501` e o Compose *concatena* `ports`, então um overlay não conseguiria fechá-las).

O que o modo produção endurece:
- **TLS + HSTS reais** no nginx (`max-age=31536000`), redirect `80 → 443`, renovação automática via certbot.
- **Rate-limit por-IP real**: `uvicorn --proxy-headers` confia no `X-Forwarded-For` só do nginx (IP fixo), então o limite por IP volta a valer atrás do proxy.
- **Fail-closed**: com `APP_ENV=production` a API **recusa iniciar** se `API_KEYS` estiver vazio ou `CORS_ORIGINS` for `*` — mesma filosofia do `EXCHANGE_DRY_RUN`.
- **Portas internas fechadas**: `8000/8501/9090` não são publicadas; só nginx (`80/443`).
- Mantém `EXCHANGE_DRY_RUN=true` — endurecer o deploy é independente de ir a real.

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
| `EXCHANGE_DRY_RUN` | **(obrigatória)** | Fonte de dados: `true` = sintético/offline · `false` = dados reais da exchange |
| `ORDER_ROUTING` | `paper` | Roteamento de ordens (independente do dado): `paper` = fills simulados · `live` = ordens reais (exige `EXCHANGE_DRY_RUN=false`). "preço real + paper" = `false` + `paper` |
| `LLM_ENABLED` / `LLM_PROVIDER` / `LLM_MODEL` | `false` / `google` / — | Camada de IA (CoT/Reflection). OFF por padrão → pipeline determinístico/offline; liga com `LLM_ENABLED=true` + chave do provider (`google`/`openai`/`anthropic`) |
| `DRY_RUN_BASE_PRICE` | `50000` | Preço-base sintético do BTC/USDT (âncora determinística) |
| `DRY_RUN_BASE_PRICES` | — | Overrides por par (`BTC/USDT=50000,ETH/USDT=3000`); pares não mapeados ganham preço determinístico próprio |
| `MARKET_PAIRS` | `BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT` | Allowlist de pares (API, loop e dashboards) |
| `SYMBOLS` | `BTC/USDT` | Pares que o loop opera por ciclo (opt-in multi-cripto; subconjunto de `MARKET_PAIRS`) |
| `AUTONOMY_LEVEL` | `2` | Nível HITL 0–3 (threshold de auto-aprovação por valor) |
| `INITIAL_CAPITAL` | `10000` | Capital base (dimensiona quantidade e métricas) |
| `LEDGER_DIR` | `.buildtovalue/ledger` | Diretório do ledger JSONL + `criptotrade.db` (montar volume em prod) |
| `ORCHESTRATOR_INTERVAL_SECONDS` | `60` | Intervalo do loop (validado 10–3600) |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` | — | LLM (Gemini primário; OpenAI backup) |
| `EXCHANGE` / `EXCHANGE_API_KEY` / `EXCHANGE_API_SECRET` / `EXCHANGE_TESTNET` | binance / … | Exchange (só usados quando `EXCHANGE_DRY_RUN=false`) |
| `API_KEYS` | — | API keys do gateway (CSV; vazio = API aberta em dev). **Obrigatória em prod** (fail-closed) |
| `APP_ENV` | — | `production` ativa o guard fail-closed (exige `API_KEYS` + `CORS_ORIGINS` explícito) |
| `CORS_ORIGINS` | `*` | Allowlist de origens CORS (CSV). Em prod **não pode** ser `*` |
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

> **Nota (dois modelos de autonomia):** o loop vivo usa o modelo **por-threshold**
> acima (`src/hitl/config.py`). Existe também um `ProgressiveAutonomyManager`
> (trust-score, `src/hitl/progressive_autonomy.py`) usado pelo `unified_orchestrator`
> — caminho alternativo. A reconciliação dos dois está adiada (ver `docs/roadmap_v1.md`).

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
| `GET /v1/process/events` | Event log XES (process mining) — ver [docs/integrations/process-mining.md](docs/integrations/process-mining.md) |
| `GET /v1/alerts` (SSE) · `GET /v1/alerts/history` | Alertas de guardrail em tempo real / histórico |

---

## 📈 Observabilidade & Escala

**Probes & métricas (Prometheus):**
- `GET /metrics` — métricas HTTP (contagem/latência por rota) **+ domínio**
  (`criptotrade_open_positions`, `criptotrade_total_trades`,
  `criptotrade_realized_pnl_usdt`, `criptotrade_win_rate`, `criptotrade_sharpe_ratio`,
  `criptotrade_portfolio_value_usdt`), lidas do ledger compartilhado (corretas
  mesmo com o loop em outro processo).
- `GET /health` (liveness) · `GET /health/ready` (readiness — checa o SQLite).
- Orchestrator (sem HTTP): heartbeat por ciclo + `scripts/healthcheck_loop.py`.

**Logs:** `LOG_FORMAT=json` ativa logs estruturados; todo request carrega
`X-Request-ID` (propagado + nos logs) para rastreio entre réplicas.

**Escala horizontal** (pronta, ativável por env/infra — ver [ADR-005](docs/adr/005-scaling-path.md)):
- API stateless → N réplicas atrás do nginx (`docker-compose.prod.yml`).
- Rate limit compartilhado: `REDIS_URL=redis://redis:6379/0` + `docker compose --profile scale up` (fail-open p/ in-memory).
- Estado compartilhado → PostgreSQL quando >1 host escrever (camada única `src/core/db.py`); loop singleton com leader election futura.

Tudo em Docker: `docker compose up -d` sobe **app, dashboard, orchestrator, prometheus**.

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
├── migrations/             # SQL versionado (001_orders_and_cycles.sql, 002_journal.sql, 003_backtest_jobs.sql)
├── config/                 # constitution.yaml, strategies/risk_params.yaml, prometheus.yml
├── docs/                   # ADRs, validação de planos, UX, tutoriais
├── tests/                  # unit, integration, emergent
├── docker-compose.yml      # serviços: app (API/dashboard), orchestrator (loop), prometheus
└── Dockerfile
```

---

## 🧪 Testes

```bash
pytest -q                                   # suíte completa (383 testes)
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
- [x] `cycles_today` cross-process · ADR-003 (persistência)
- [x] Rate limiting (30 req/min escrita / 200 leitura), security headers, confirmação em mutações sensíveis (Sprint A / P0)
- [x] Validação de par de mercado (allowlist `MARKET_PAIRS`), backtest jobs persistidos em SQLite, doc de integração PM4Py (Sprint B / P2)
- [x] Console React (esbuild), nginx TLS/certbot, Sentry, OpenAPI snapshot, E2E Playwright, pipeline de deploy (Sprint C / P3)
- [x] Tech-debts 5b (`_last_order_ref`, `wait_for_decision`, stubs, pruning de `cycle_events`), ledger JSONL→SQLite WAL (Fase 5b)

### 🔜 Pendente (ação do dono — ver `docs/acaoPendenteDono.md`)
- [x] Tech debts `TODO(5b)` (reset de `_last_order_ref`, `wait_for_decision` com id inexistente, default de `position_size_pct`) — PR #48
- [x] Pruning de `cycle_events` (`AgentRegistry.prune_cycle_events`, retenção 30d, no startup do loop e na virada do dia)
- [x] Filtrar agentes `not_implemented` no dashboard (toggle, ocultos por padrão) — PR #48; paginação em `/v1/orders` já existia
- [ ] **Migração XES events → SQLite (fecha ADR-003)** — **adiada deliberadamente**. O ADR-003 trata isso como decisão de planejamento (não de pressão de produção) e exige preservar o contrato `get_events`/`read_all` do ledger; na prática a maioria dos agentes são stubs, então o volume real fica bem abaixo do limiar de ~10k eventos/dia que justificaria a migração. Reabrir quando o volume sustentado passar do limiar.

---

## 🤝 Contribuindo

Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`). Abra PRs contra `master`; a CI precisa passar (testes + ruff).

---

## ⚠️ Disclaimer

Software fornecido "como está", sem garantias. Trading de cripto envolve risco substancial de perda. Fase de **paper trading / pesquisa** — não é aconselhamento financeiro. DYOR.

## 📄 Licença

[MIT License](LICENSE).
