# Arquitetura — Criptotrade (visão completa deste repositório)

> Conjunto completo de **diagramas de arquitetura** de **todo este repositório**, no modelo **C4** (Contexto → Contêineres → Componentes) + vistas de apoio (dados/ERD, fluxo de dados, runtime, implantação, CI/CD, observabilidade, segurança) e **recomendações de arquitetura** com um estado-alvo proposto.
>
> Complementa `docs/uml/arquitetura-uml.md` (que detalha as **classes**). Aqui o foco é o **nível arquitetural**: sistemas, contêineres, integrações, dados, deploy e evolução.
>
> **Composição do repositório:** Python (backend, ~168 arq.), React/JSX (console em `docs/design/pages/`), 1 arquivo TypeScript gerado (`openapi.d.ts`, o contrato), infra (Docker/nginx/Prometheus/Grafana). Sem Rust.

## Índice
1. [C4 L1 — Contexto de Sistema](#1-c4-nível-1--contexto-de-sistema)
2. [C4 L2 — Contêineres](#2-c4-nível-2--contêineres)
3. [C4 L3 — Componentes: API](#3-c4-nível-3--componentes-do-contêiner-api)
4. [C4 L3 — Componentes: Loop Orquestrador](#4-c4-nível-3--componentes-do-contêiner-loop-orquestrador)
5. [Arquitetura de Dados (ERD + stores)](#5-arquitetura-de-dados)
6. [Fluxo de Dados (DFD)](#6-fluxo-de-dados-dfd)
7. [Vista de Runtime / Processos](#7-vista-de-runtime--processos)
8. [Implantação (3 topologias)](#8-implantação)
9. [Pipeline CI/CD](#9-pipeline-cicd)
10. [Arquitetura de Observabilidade](#10-arquitetura-de-observabilidade)
11. [Arquitetura de Segurança](#11-arquitetura-de-segurança)
12. [Recomendações e Arquitetura-Alvo](#12-recomendações-de-arquitetura-e-estado-alvo)

**Legenda de estereótipos (C4):** `«person»` ator humano · `«system»` sistema externo · `«container»` unidade executável/deployável (processo, app, banco) · `«component»` agrupamento lógico dentro de um contêiner. Setas = fluxo/dependência rotulada com protocolo.

---

## 1. C4 Nível 1 — Contexto de Sistema

**Objetivo:** o sistema Criptotrade como uma caixa preta, seus usuários e sistemas externos.

```mermaid
graph TB
    Op(["👤 Operador / Trader<br/>«person»<br/>aprova ordens (HITL), ajusta risco,<br/>observa KPIs"])

    subgraph SYSBND["Criptotrade — Plataforma de Trading com IA + HITL «system»"]
        SYS["Backend Python + Console Web<br/>gera sinais, valida risco, executa<br/>ordens (paper), audita tudo"]
    end

    EX(["🏦 Exchange / Market Data<br/>«system» (CCXT)<br/>OHLCV, ordens (paper por padrão)"])
    LLM(["🧠 LLM Provider<br/>«system» (Gemini/OpenAI/Anthropic)<br/>Chain-of-Thought / reflexão (opcional)"])
    PROM(["📈 Prometheus + Grafana<br/>«system»<br/>métricas técnicas e de negócio"])
    SENTRY(["🐞 Sentry<br/>«system» (opcional)<br/>captura de erros 5xx"])

    Op -->|"HTTPS: console React + dashboard Streamlit"| SYS
    SYS -->|"CCXT (async); dry-run offline por padrão"| EX
    SYS -.->|"HTTPS (opcional, degradação graciosa)"| LLM
    PROM -->|"scrape /metrics (HTTP, 15s)"| SYS
    SYS -.->|"eventos 5xx (opcional)"| SENTRY
```

**Notas de arquitetura:**
- **HITL é primeira-classe:** o operador não é observador passivo — é parte do fluxo de execução (aprova/rejeita ordens acima do limiar de autonomia).
- **Fail-safe por padrão:** o único caminho para a exchange roda em `EXCHANGE_DRY_RUN=true` (mercado sintético offline); trading real exige override explícito no ambiente de deploy.
- **Dependências externas são todas opcionais/degradáveis:** LLM, Sentry e até a exchange (dry-run) podem faltar sem derrubar o núcleo.

---

## 2. C4 Nível 2 — Contêineres

**Objetivo:** as unidades executáveis/deployáveis e como se comunicam. Este é o diagrama de arquitetura central.

```mermaid
graph TB
    Op(["👤 Operador «person»"])

    subgraph Boundary["Criptotrade «system»"]
        NGINX["nginx «container»<br/>reverse proxy + TLS<br/>serve console estático · proxy /v1"]
        CONSOLE["Console React «container»<br/>docs/design/pages (dist estático)<br/>SPA hash-routing"]
        API["API «container»<br/>FastAPI/uvicorn :8000<br/>REST /v1 + SSE + /metrics"]
        LOOP["Loop Orquestrador «container»<br/>python -m src.orchestration.main_loop<br/>ciclo de trading (sem porta)"]
        DASH["Dashboard «container»<br/>Streamlit :8501<br/>console operacional alternativo"]
        SQLITE[("SQLite (WAL) «container»<br/>orders · cycle_events · open_positions<br/>circuit_breaker · backtest_jobs · journal · ledger_events")]
        JSONL[("Arquivos append-only «container»<br/>ledger JSONL · alerts JSONL · XES · memória")]
        PROM["Prometheus «container» :9090"]
        GRAF["Grafana «container» :3000"]
        PG[("Postgres «container» (perfil scale)")]
        REDIS[("Redis «container» (perfil scale)")]
    end

    EX(["Exchange (CCXT) «system»"])
    LLM(["LLM «system»"])

    Op -->|HTTPS| NGINX
    NGINX -->|serve estático| CONSOLE
    CONSOLE -->|"REST /v1 + SSE (envelope APIResponse, X-API-Key)"| NGINX
    NGINX -->|"HTTP proxy /v1 /health"| API
    Op -.->|HTTP alternativo| DASH
    DASH -->|"httpx REST /v1"| API

    API -->|read/write| SQLITE
    API -->|read/write| JSONL
    LOOP -->|read/write| SQLITE
    LOOP -->|append| JSONL
    LOOP -->|analyze_and_trade| EX
    API -->|market data| EX
    LOOP -.->|CoT/reflexão| LLM
    API -.->|CoT| LLM

    PROM -->|scrape /metrics| API
    GRAF -->|query| PROM
    API -. "scale: DATABASE_URL" .-> PG
    API -. "scale: REDIS_URL (rate limit)" .-> REDIS

    classDef store fill:#e8eef7,stroke:#4a6fa5;
    class SQLITE,JSONL,PG,REDIS store;
```

**Decisões arquiteturais-chave (o "porquê"):**

| Decisão | Racional | ADR |
|---|---|---|
| **API e Loop como contêineres separados** | Lifecycle independente: restart da API não para o trading, e vice-versa | ADR-002 |
| **Estado compartilhado via SQLite WAL** (sem RPC/fila) | Cross-process simples e durável; dois processos no mesmo host/volume | ADR-001/003 |
| **Paper trading first (`EXCHANGE_DRY_RUN`)** | Segurança: zero conexão real por padrão | ADR-001 |
| **Uma imagem Python para API/Loop/Dashboard** | Diferem só pelo `command`; simplifica build/deploy | — |
| **Console React estático (esbuild + nginx)** | Sem servidor Node em produção; SPA servida como arquivos | — |
| **Postgres/Redis opt-in (perfil `scale`)** | Escala horizontal sem mudar código (abstração de DB + rate limiter) | ADR-005 |

---

## 3. C4 Nível 3 — Componentes do Contêiner API

**Objetivo:** organização interna da FastAPI (`src/api/*`).

```mermaid
graph TB
    subgraph API["Contêiner API (FastAPI) «container»"]
        direction TB
        MW["Cadeia de Middleware «component»<br/>RequestId → Prometheus → RateLimit →<br/>SecurityHeaders → CORS → APIKey"]
        subgraph Routers["Routers /v1 «component»"]
            R1[metrics · trades · risk]
            R2[orders · hitl]
            R3[agents · config · process]
            R4[market · backtest · journal · alerts]
        end
        DEPS["deps.py «component»<br/>providers @lru_cache:<br/>ledger · order_store · alert_store/bus ·<br/>registry · exchange · metrics_calc · hitl_store"]
        SCHEMAS["schemas.py «component»<br/>DTOs Pydantic + envelope APIResponse[T]"]
        OBS["observability «component»<br/>PrometheusMiddleware · DomainMetricsCollector"]
    end

    subgraph Domain["Serviços de domínio/infra (fora da API)"]
        OS["OrderStore (hitl)"]
        LG["TradingLedger (core)"]
        MC["PortfolioMetricsCalculator"]
        AR["AgentRegistry"]
        AX["ExchangeClient + analysis/*"]
        BT["BacktestEngine/MC/WF"]
        AB["AlertStore + AlertBus"]
    end
    DB[("SQLite/Postgres")]

    MW --> Routers
    Routers --> DEPS
    Routers --> SCHEMAS
    DEPS --> OS
    DEPS --> LG
    DEPS --> MC
    DEPS --> AR
    DEPS --> AX
    R2 --> OS
    R4 --> BT
    R4 --> AB
    R4 --> AX
    R1 --> MC
    OS --> DB
    LG --> DB
    OBS --> LG
```

**Notas:**
- **Middleware em cadeia (fail-closed em prod):** `_enforce_prod_security()` recusa boot em produção sem `API_KEYS` + `CORS_ORIGINS` explícito. Rate limit por IP real (nginx repassa `X-Forwarded-*`).
- **Injeção via `deps.py`:** providers `@lru_cache(maxsize=1)` (singletons por processo), exceto `get_metrics_calculator` (fresco a cada request para refletir o ledger). `reset_singletons()` para testes.
- **Contrato tipado:** `schemas.py` → OpenAPI → `openapi.d.ts` (gate de drift no CI).

---

## 4. C4 Nível 3 — Componentes do Contêiner Loop Orquestrador

**Objetivo:** organização interna do processo de trading (`src/orchestration/*` + agentes).

```mermaid
graph TB
    subgraph LOOP["Contêiner Loop «container»"]
        MAIN["main_loop «component»<br/>init_db · from_env · sinais SIGTERM"]
        OL["OrchestratorLoop «component»<br/>run_forever/run_cycle · intervalo 60s ·<br/>heartbeat · registry.record_cycle"]
        SQ["SquadOrchestrator «component»<br/>pipeline analyze_and_trade"]
        CB["CircuitBreaker «component»<br/>perda diária 4% / 3 losses → pausa 24h"]
        subgraph Agents["Agentes de trading «component»"]
            SA[StrategyAgent<br/>CoT + TA + regime]
            RA[RiskAgent<br/>reflexão + guardrails]
            EA[ExecutionAgent<br/>ReAct paper fill]
        end
        PS["PositionStore «component»<br/>book de posições paper"]
        HB["approval_handler «component»<br/>OrderStore.wait_for_decision"]
    end
    DB[("SQLite compartilhado")]
    EX(["Exchange (CCXT)"])
    LG["TradingLedger + XES"]

    MAIN --> OL
    OL --> SQ
    SQ --> CB
    SQ --> SA
    SQ --> RA
    SQ --> EA
    SQ --> PS
    SQ --> HB
    SA --> EX
    EA --> EX
    HB --> DB
    PS --> DB
    CB --> DB
    OL --> LG
    SQ --> LG
```

**Notas:**
- **Pipeline invariante:** `Strategy → (fecha SL/TP) → Risk → Guardrails → HITL → Execution → fill/ledger`, com circuit breaker no início. Fail-soft: falha de um símbolo emite `agent_cycle_failed` e o loop continua.
- **Recuperação de restart:** `reload_open_positions()` restaura book + breaker do SQLite (evita posições zumbi / streak esquecida).
- Detalhe de classes e sequência: ver `docs/uml/arquitetura-uml.md` §5.2 e §6.1.

---

## 5. Arquitetura de Dados

**Objetivo:** o modelo de persistência. O sistema usa **dois estilos**: (a) tabelas SQLite/Postgres para estado cross-process, (b) arquivos append-only (JSONL/JSON) para auditoria e memória.

### 5.1 ERD — estado relacional (SQLite WAL / Postgres)

```mermaid
erDiagram
    orders {
        TEXT id PK "ord_xxxx"
        TEXT pair
        TEXT side "buy|sell (CHECK)"
        REAL quantity "> 0"
        REAL price "> 0"
        TEXT strategy
        TEXT agent_id
        REAL confidence
        INTEGER critical "0/1"
        REAL position_size_pct
        REAL stop_loss
        REAL take_profit
        TEXT status "pending|approved|filled|rejected|cancelled"
        INTEGER auto_approved "0/1"
        TEXT created_at
        TEXT resolved_at
        TEXT filled_at
    }
    open_positions {
        TEXT order_id PK
        TEXT symbol
        TEXT side
        REAL entry_price
        REAL quantity
        REAL stop_loss
        REAL take_profit
        TEXT opened_at
    }
    circuit_breaker_state {
        INTEGER id PK "singleton (id=1)"
        REAL tripped_at
        INTEGER consecutive_losses
        REAL daily_loss_pct
    }
    cycle_events {
        INTEGER id PK "autoincrement"
        TEXT agent_id
        TEXT cycled_at "idx(agent_id,cycled_at)"
    }
    backtest_jobs {
        TEXT id PK
        TEXT status "running|done|error"
        TEXT config_json
        TEXT result_json
        TEXT error
        TEXT created_at
        TEXT completed_at
    }
    journal_entries {
        INTEGER id PK "autoincrement"
        TEXT setup
        INTEGER emotion_before "1..10"
        INTEGER emotion_after "1..10"
        INTEGER stop_defined "0/1"
        INTEGER plan_followed "0/1"
        REAL pnl_pct
        TEXT created_at
    }
    ledger_events {
        INTEGER id PK "autoincrement"
        TEXT timestamp
        TEXT event_type "idx"
        TEXT data "JSON"
    }

    orders ||..o| open_positions : "id ≈ order_id (lógico, sem FK)"
    orders ||..o{ ledger_events : "gera eventos (lógico)"
    cycle_events }o..|| orders : "agent_id (lógico)"
```

> **Nota de design importante:** as tabelas **não têm foreign keys** entre si. É deliberado — são datasets de coordenação cross-process (bridge HITL, contadores, book) desenhados para escrita concorrente por dois processos sem contenção de lock. As relações acima são **lógicas** (tracejadas). O `ledger_events` é o *event store* de onde métricas são derivadas.

### 5.2 Data stores completos (relacional + arquivos)

```mermaid
graph LR
    subgraph Relacional["SQLite WAL (default) / Postgres (scale)"]
        T1[orders]
        T2[open_positions]
        T3[circuit_breaker_state]
        T4[cycle_events]
        T5[backtest_jobs]
        T6[journal_entries]
        T7[ledger_events]
    end
    subgraph Arquivos["Append-only (volume ./data)"]
        F1[["ledger JSONL<br/>auditoria"]]
        F2[["event log XES<br/>process mining"]]
        F3[["alerts JSONL"]]
        F4[["agent_memories.jsonl<br/>+ Chroma opcional"]]
        F5[["trade_journal.json"]]
        F6[["loop_heartbeat.json"]]
    end
    Writers["API · Loop · Agentes"] --> Relacional
    Writers --> Arquivos
    Metrics["PortfolioMetricsCalculator"] -->|deriva| T7
    ProcessAPI["/v1/process/events"] -->|lê| F2
```

**Notas:**
- **Event Sourcing leve:** métricas de portfólio (Sharpe, win rate, drawdown, P&L) **não são armazenadas** — são recalculadas relendo `ledger_events` (`position_closed`, `order_fill`). Fonte única de verdade.
- **Migração de portabilidade:** `src/core/db.py` abstrai `connection()`; migrations em `migrations/` (+ `migrations/postgres/`) rodadas por `init_db()` (idempotente, ambos processos).
- **Dívida conhecida (ADR-003):** o XES/alerts ainda em JSONL; a migração completa para SQLite está deferida.

---

## 6. Fluxo de Dados (DFD)

**Objetivo:** como um sinal vira ordem, fill e métrica — o caminho do dado ponta a ponta.

```mermaid
flowchart LR
    EX([Exchange OHLCV]) -->|fetch_ohlcv| SA[StrategyAgent<br/>TA + regime + CoT]
    SA -->|signal + confidence| RA[RiskAgent + Guardrails]
    RA -->|approved signal| OSUB[OrderStore.submit]
    OSUB -->|"notional ≤ threshold?"| AUTO{auto?}
    AUTO -->|sim| FILL[fill local]
    AUTO -->|não| PEND[(orders: pending)]
    PEND -->|"PATCH /v1/orders (operador)"| APPR[(orders: approved)]
    APPR -->|loop wait_for_decision| EXEC[ExecutionAgent paper fill]
    FILL --> LED[(ledger_events)]
    EXEC --> LED
    LED -->|position_closed / order_fill| MC[PortfolioMetricsCalculator]
    MC -->|APIResponse| UI[Console / Dashboard]
    RA -.->|rejeição| AL[(alerts)]
    AL -.->|SSE /v1/alerts| UI
    LED -.->|XES| PM["/v1/process/events → process mining"]
```

**Notas:** dois "portões" no fluxo — **guardrails** (risco por ordem) e **HITL** (aprovação por valor). Todo evento econômico passa pelo ledger, do qual métricas e process mining derivam.

---

## 7. Vista de Runtime / Processos

**Objetivo:** o que roda concorrentemente e como sincronizam.

```mermaid
graph TB
    subgraph P1["Processo: API (uvicorn) — N workers possíveis"]
        A1[event loop asyncio]
        A2[middleware + routers]
        A3[backtest asyncio.create_task]
    end
    subgraph P2["Processo: Loop — SINGLE INSTANCE"]
        B1[run_forever: ciclo a cada 60s]
        B2[wait_for_decision: poll 2s]
    end
    subgraph P3["Processo: Dashboard (Streamlit)"]
        C1[httpx → API]
    end
    SHARED[("SQLite WAL<br/>(única fonte de sincronização)")]

    A2 -->|resolve/decide| SHARED
    B2 -->|poll status| SHARED
    B1 -->|record_cycle / positions| SHARED
    A3 -->|persist jobs| SHARED
    C1 -->|HTTP| A2

    note1["Sincronização = estado no SQLite.<br/>Sem fila/mensageria.<br/>Latência de aprovação ≤ poll_interval (2s).<br/>Timeout 300s → cancel (fail-closed)."]
    P2 -.-> note1
```

**Ponto de atenção arquitetural:** o **loop é single-instance por design** (ADR-005). O modelo HITL por *polling* de SQLite não é trivialmente replicável para N loops (precisaria de leader-election ou locks de linha). A API, sim, escala horizontalmente (estado externo + rate limiter Redis).

---

## 8. Implantação

**Objetivo:** as três topologias versionadas. Nós = contêineres; setas rotuladas com protocolo/porta.

### 8.1 Dev — `docker-compose.yml`

```mermaid
graph TB
    Host["🖥️ Host dev (todas as portas publicadas)"]
    app["app :8000<br/>EXCHANGE_DRY_RUN=true"]
    orch["orchestrator (sem porta)<br/>INTERVAL=60s"]
    dash["dashboard :8501"]
    prom["prometheus :9090"]
    graf["grafana :3000"]
    pg["postgres :5432<br/>(perfil scale)"]
    rd["redis :6379<br/>(perfil scale)"]
    vol[("volume ./data + ./logs<br/>compartilhado app↔orchestrator")]

    Host --- app & orch & dash & prom & graf & pg & rd
    app --- vol
    orch --- vol
    dash -->|API_URL=http://app:8000| app
    prom -->|scrape| app
    graf -->|query| prom
    app -. scale .- pg
    app -. scale .- rd
    orch -->|healthcheck| hc["scripts/healthcheck_loop.py<br/>(lê loop_heartbeat.json)"]
```

### 8.2 Prod self-contained — `docker-compose.prod.yml`

```mermaid
graph TB
    Net["rede edge 172.28.0.0/24 (nginx = .2)"]
    subgraph Public["Exposto (host)"]
        nginx["nginx :80/:443<br/>console baked + proxy /v1<br/>reload a cada 6h"]
        certbot["certbot sidecar<br/>renova certs 2x/dia (HTTP-01)"]
    end
    subgraph Internal["Interno (sem porta de host)"]
        appp["app<br/>--proxy-headers<br/>--forwarded-allow-ips 172.28.0.2<br/>APP_ENV=production (fail-closed)"]
        orchp["orchestrator"]
        promp["prometheus"]
    end
    volp[("volume ./data")]
    Browser(["Browser"])

    Browser -->|HTTPS 443| nginx
    nginx -->|HTTP proxy| appp
    certbot -.-> nginx
    appp --- volp
    orchp --- volp
    promp -->|scrape| appp
    Net --- nginx & appp & orchp & promp
```

### 8.3 VPS atrás de gateway compartilhado — `docker-compose.vps.yml`

```mermaid
graph LR
    GW["btv-nginx-prod (global-ingress)<br/>rede externa btv-prod-net"]
    subgraph CT["rede interna criptotrade_internal (expose only)"]
        va["criptotrade-app:8000"]
        vf["criptotrade-frontend:80<br/>(console.Dockerfile)"]
        vd["criptotrade-dashboard:8501"]
        vo["criptotrade-orchestrator"]
        vp["criptotrade-prometheus"]
    end
    GW -->|"/v1/ ·/health → app:8000"| va
    GW -->|"/ → frontend:80"| vf
    vf -->|"same-origin /v1 (API_BASE='')"| GW
    vd --> va
    vp --> va
```

**Notas:**
- **Superfície pública mínima em prod:** só nginx/gateway publica 80/443; app/loop/prometheus ficam internos.
- **Confiança de proxy explícita:** app só aceita `X-Forwarded-*` de `172.28.0.2` → rate-limit por IP real.
- **Uma imagem Python** reusada; console em imagem nginx separada (`deploy/console.Dockerfile`, multi-stage node→nginx).

---

## 9. Pipeline CI/CD

**Objetivo:** os gates automáticos (GitHub Actions) que protegem `master`.

```mermaid
flowchart TB
    TRIG["push master / claude/**  ·  PR → master"]

    subgraph WF1["workflow: Python CI"]
        SS["secret-scan<br/>gitleaks"]
        TEST["test<br/>ruff (gate correção) + ruff full (info)<br/>pytest --cov (fail-under 72%)"]
        DB2["docker-build (needs: test)<br/>build imagem Python · compose config -q (prod+vps)<br/>build console image · nginx -t (certs efêmeros)"]
        CB["console-build<br/>npm ci · npm run build (esbuild)<br/>gen:types + git diff --exit-code (drift gate)<br/>upload console-dist"]
        E2E["console-e2e<br/>build · playwright chromium (mock data)"]
    end
    subgraph WF2["workflow: Phase 1-3 Validation (rápido)"]
        PV["validate-phases<br/>lean deps · ruff módulos novos<br/>smoke import src.api.main:app<br/>pytest (metrics/alerts/db/api/orders)"]
    end

    TRIG --> SS & TEST & CB & E2E & PV
    TEST --> DB2

    style DB2 fill:#eef7ee,stroke:#4a7
    style CB fill:#eef7ee,stroke:#4a7
```

**Gates notáveis:**
- **Drift do contrato** (`gen:types` + `git diff --exit-code openapi.d.ts`): backend Python e front JS **não podem divergir**.
- **Compose/nginx validados no CI** com certs auto-assinados descartáveis.
- **Cobertura com piso** (`--cov-fail-under=72`, `pyproject.toml`), com meta de subir para 80%.
- **Dois workflows**: um completo (pesado) e um rápido por fases (deps enxutas).

---

## 10. Arquitetura de Observabilidade

**Objetivo:** os quatro pilares — métricas, logs, traces, e o diferencial de **process mining**.

```mermaid
graph TB
    subgraph App["API + Loop"]
        PM["PrometheusMiddleware<br/>http_requests_total · duration histogram<br/>(label = template de rota, cardinalidade limitada)"]
        DM["DomainMetricsCollector<br/>criptotrade_* gauges do ledger<br/>(open_positions, pnl, win_rate, sharpe)"]
        LOG["Logs JSON estruturados<br/>python-json-logger + request_id<br/>(RequestIdMiddleware + ContextVar)"]
        TR["AgentObserver / SpanRecord<br/>trajectory export (reasoning log)"]
        XES["TradingLedger.log_process_event<br/>event log XES (case_id, activity, actor)"]
        HB["loop_heartbeat.json<br/>liveness do loop (sem HTTP)"]
        SEN["Sentry (opcional)<br/>captura 5xx"]
    end

    PROM["Prometheus :9090<br/>scrape /metrics (15s)"]
    GRAF["Grafana :3000<br/>dashboards provisionados<br/>(performance/availability/business/ai)"]
    PMINE["/v1/process/events<br/>→ análise de processo"]
    SSE["/v1/alerts (SSE)<br/>AlertBus fan-out"]

    PM --> PROM
    DM --> PROM
    PROM --> GRAF
    XES --> PMINE
    App --> SSE
    HB --> HCK["scripts/healthcheck_loop.py"]
    SEN -.-> SentryCloud([Sentry])
```

**Diferencial:** o **event log XES** (`log_process_event` emite `agent_cycle_started/completed/failed`, `order_submitted/approved/rejected/filled/cancelled`) habilita *process mining* real do fluxo de trading — raro em sistemas deste porte. Correlação por `request_id` liga logs a requests HTTP.

---

## 11. Arquitetura de Segurança

**Objetivo:** as camadas de defesa (rede, autenticação, risco, execução, segredos).

```mermaid
graph TB
    subgraph Perimetro["Perímetro"]
        N["nginx/gateway<br/>TLS 1.2/1.3 · HSTS · único público"]
    end
    subgraph Rede["Isolamento de rede"]
        NET["app/loop/prom internos<br/>(edge 172.28.0.0/24 ou criptotrade_internal)<br/>--forwarded-allow-ips (confia só no proxy)"]
    end
    subgraph AppSec["Segurança da aplicação (middleware)"]
        AUTH["APIKeyMiddleware (X-API-Key)<br/>dev: fail-open · prod: fail-closed<br/>(_enforce_prod_security no boot)"]
        RL["RateLimitMiddleware<br/>30/min write · 200/min read (por IP)"]
        SH["SecurityHeadersMiddleware<br/>CSP · X-Frame-Options DENY · nosniff · HSTS"]
        CORS["CORS: '*' dev / allowlist explícito prod"]
    end
    subgraph Trading["Segurança de trading"]
        DRY["EXCHANGE_DRY_RUN obrigatório<br/>(ExchangeClient recusa iniciar sem)"]
        GR["GuardrailSystem<br/>position size · stop loss · risk-reward"]
        HITL["HITL fail-closed<br/>(sem handler → nega)"]
        CBK["CircuitBreaker (perda diária/streak)"]
    end
    subgraph Exec["Segurança de execução (tools)"]
        SC["SecurityConfig<br/>FORBIDDEN_PATTERNS · validate_tool_call"]
        SB["SecureToolSandbox<br/>DockerSandbox (network off, timeouts)"]
    end
    subgraph Segredos["Gestão de segredos"]
        GL["gitleaks (CI)"]
        ENV[".env / .env.prod (host, fora do git)"]
    end

    N --> NET --> AppSec --> Trading
    AppSec -.-> Exec
    Segredos -.-> AppSec
```

**Notas:**
- **Fail-closed onde importa:** produção recusa boot com auth aberto; HITL nega sem handler; exchange recusa sem `EXCHANGE_DRY_RUN`.
- **Defesa em profundidade:** perímetro (TLS) → rede (isolamento) → app (auth/rate/headers) → domínio (guardrails/HITL/breaker) → execução (sandbox).
- **Pontos a consolidar** (ver §12): duas políticas de validação de ordem (`GuardrailSystem` vs `SecurityConfig.validate_order`) e dois modelos de autonomia.

---

## 12. Recomendações de Arquitetura e Estado-Alvo

### 12.1 Achados priorizados

| # | Severidade | Achado | Recomendação |
|---|---|---|---|
| R1 | 🔴 Alta | **Cluster "BuildToValue" paralelo** (`UnifiedOrchestrator` + planning/routing/consensus/chains/parallel + agentes de engenharia) **não exercitado pelo trading** | Extrair para pacote opcional `src/experimental/` ou remover; medir cobertura real. Reduz superfície e confusão. |
| R2 | 🔴 Alta | **Colisões de nome** (`SquadOrchestrator`×2, `AdaptivePlanner`×2, `ContinuousEvaluator`×2, `MemoryStore`×2, `Guardrail`×2) | Renomear por propósito (ex.: `TradingSquad` vs `A2ASquad`). Evita imports errados. |
| R2b | 🟠 Média | **Duas fundações de agente** (`BaseAgent` async vs `SafeAgentBase` sync) sem ponte | Escolher uma base única ou documentar explicitamente os dois papéis. |
| R3 | 🟠 Média | **Duas políticas de validação de ordem** e **dois modelos de autonomia** (US$ threshold vs trust-score) | Eleger fonte única de política de risco/autonomia. |
| R4 | 🟠 Média | **HITL por polling de SQLite** acopla loop↔API ao arquivo; loop single-instance | Migrar coordenação para **Postgres `LISTEN/NOTIFY`** ou Redis pub/sub → menor latência + caminho para multi-loop. |
| R5 | 🟡 Baixa | **Kelly/proteções prontos mas não plugados** no sizing do pipeline | Ligar `PositionSizer`/`KellyCriterion`/`CapitalProtections` no `SquadOrchestrator._position_quantity`. |
| R6 | 🟡 Baixa | **Namespace `/v1/agents/...` servido por dois routers** (`agents` e `config`) | Consolidar num router único. |
| R7 | 🟡 Baixa | **XES/alerts ainda em JSONL** (ADR-003 deferido) | Concluir migração para SQLite/Postgres quando o volume justificar. |
| R8 | 🟡 Baixa | **Frontend "classic scripts" com globals `window.*`** | Migrar para ES modules + bundler quando o console crescer. |

### 12.2 Métricas qualitativas de acoplamento
- **Núcleo estável correto:** `core` é dependência de quase tudo e depende de pouco (config/db) — *Stable Dependencies Principle* respeitado.
- **God Object no cluster genérico:** `UnifiedOrchestrator` compõe 9 subsistemas — acoplamento eferente alto, reforça R1.
- **Bom uso de inversão de dependência:** callbacks (`alert_sink`, `state_db_provider`, `fill_callback`, `approval_handler`) quebram ciclos de import consistentemente.

### 12.3 Arquitetura-alvo proposta (evolução incremental)

```mermaid
graph TB
    Op(["👤 Operador"])
    subgraph Target["Estado-alvo"]
        NGINX["nginx/gateway (TLS)"]
        FE["Console (ES modules + bundler)"]
        API["API FastAPI (N réplicas)"]
        subgraph Loops["Loop(s) de trading"]
            L1["Loop primário (leader)"]
            L2["Loop standby (leader-election)"]
        end
        BUS{{"Coordenação:<br/>Postgres LISTEN/NOTIFY<br/>ou Redis pub/sub"}}
        PGDB[("Postgres<br/>estado + event store XES unificado")]
        RISK["Serviço de Risco único<br/>(GuardrailSystem + Kelly + proteções)"]
        OBS["Observabilidade<br/>Prometheus + Grafana + traces"]
    end
    EX(["Exchange"])
    LLM(["LLM (opcional)"])

    Op -->|HTTPS| NGINX --> FE
    FE -->|REST+SSE| API
    API --> BUS
    L1 --> BUS
    L2 -. standby .-> BUS
    API --> PGDB
    L1 --> PGDB
    L1 --> RISK
    API --> RISK
    L1 --> EX
    L1 -.-> LLM
    API --> OBS
    L1 --> OBS

    style BUS fill:#fff3cd,stroke:#c90
    style RISK fill:#d4edda,stroke:#4a7
    style Loops fill:#e8eef7,stroke:#4a6fa5
```

**Roteiro incremental (sem big-bang):**
1. **Higiene** (R1, R2): isolar/remover o cluster genérico e renomear colisões — baixo risco, alto ganho de clareza.
2. **Consolidação de política** (R3, R5, R6): uma fonte de risco/autonomia; plugar Kelly; unificar rotas de agentes.
3. **Coordenação** (R4, R7): trocar polling SQLite por `LISTEN/NOTIFY` no Postgres (já suportado pela abstração de DB) e unificar o event store — habilita multi-loop com leader-election.
4. **Frontend** (R8): migrar para ES modules/bundler.

Cada passo é independente e preserva o invariante central: **paper-trading-first, HITL fail-closed, tudo auditável no ledger/XES**.

---

> **Diagramas em Mermaid** (renderizam nativamente no GitHub). Nomes de contêineres/componentes/tabelas preservados conforme o código-fonte e migrations. Para detalhe de **classes** e sequências, ver `docs/uml/arquitetura-uml.md`.
