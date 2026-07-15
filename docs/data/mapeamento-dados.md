# Mapeamento Completo de Dados — Criptotrade

> **Dicionário de dados exaustivo de todo o repositório.** Mapeia **todos os dados que circulam no sistema** — entradas, saídas, processamento intermediário e estado — em cada módulo e em cada linguagem (Python, JavaScript/JSX, TypeScript, HTML, SQL, YAML, `.env`, Docker). Inclui deliberadamente os dados **"perdidos na própria classe"** (atribuídos e nunca lidos).
>
> Produzido por análise estática dos scripts do repositório, com referências `arquivo:linha`. Complementa `docs/uml/arquitetura-uml.md` (classes) e `docs/architecture/arquitetura.md` (C4).
>
> ℹ️ **Atualização 2026-07-14:** parte das anomalias de §9 e dos dados mortos de §8
> já foram corrigidos na "Onda 1" — ver **`docs/plano-melhorias.md`** para o estado
> vivo (ex.: §9.3 `mean_reversion` agora roteável, §9.4 `ab_tests.jsonl` em JSON
> válido, e vários dados de §8 removidos). Este documento permanece como o **retrato
> de análise estática** do momento em que foi gerado.

## Nota sobre linguagens
Varredura recursiva do repositório: **Python** 168 arquivos (núcleo), **React/JSX + JS** ~24 (console em `docs/design/pages/`), **TypeScript** 1 (`openapi.d.ts`, contrato gerado), **HTML** 2, **SQL** 4 (migrations), **YAML** vários (config/monitoring). **Rust: 0 arquivos** — não existe código Rust neste repositório; onde a metodologia pediria mapeamento Rust, registra-se a ausência.

## Legenda de classificação de dado
Cada dado é marcado por seu papel no fluxo:

| Marca | Papel |
|---|---|
| **E** | Entrada (input externo: parâmetro, env, HTTP, arquivo, exchange, LLM) |
| **S** | Saída (retorno de função, resposta HTTP, escrita em store, alerta) |
| **I** | Intermediário (variável local, atributo de estado, dict transformado) |
| **P** | Persistido (SQLite/Postgres, JSONL/JSON, arquivo) |
| **X** | Dado morto / "perdido na classe" (atribuído e nunca lido depois) |

---

## Índice
- [1. Dados de entrada — configuração e ambiente](#1-dados-de-entrada--configuração-e-ambiente)
- [2. Dados persistidos — bancos e arquivos](#2-dados-persistidos--bancos-e-arquivos)
- [3. Estruturas de dados canônicas em trânsito](#3-estruturas-de-dados-canônicas-em-trânsito)
- [4. Catálogo por módulo — backend Python](#4-catálogo-por-módulo--backend-python)
- [5. Dados da camada API (DTOs, rotas, middleware)](#5-dados-da-camada-api)
- [6. Dados do frontend (React/JS) e contrato TS](#6-dados-do-frontend-reactjs-e-contrato-ts)
- [7. Ciclo de vida ponta-a-ponta de um dado](#7-ciclo-de-vida-ponta-a-ponta-de-um-dado)
- [8. Dados "perdidos na classe" / declarados-mas-não-usados](#8-dados-perdidos-na-classe--declarados-mas-não-usados)
- [9. Anomalias e inconsistências de dados](#9-anomalias-e-inconsistências-de-dados)

---

## 1. Dados de entrada — configuração e ambiente

### 1.1 Variáveis de ambiente (todas as lidas no código)

| Var | Default | Tipo/coerção | Consumido em |
|---|---|---|---|
| `APP_ENV` | `"development"` | str, compara `"production"` | `config.py:16`, `api/main.py:67,195`, `routes/config.py:62` |
| `LOG_LEVEL` | `"INFO"` | str | `config.py:17` |
| `LOG_FORMAT` | `"text"` | text\|json | `config.py:18` |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | `None` | str | `config.py:21-22`, `llm_client.py:51-54` |
| `LLM_ENABLED` | `false` | truthy (`1/true/yes/on`) | `llm_client.py:61` |
| `LLM_PROVIDER` | `"google"` | str | `llm_client.py:47` |
| `LLM_MODEL` | (default por provider) | str | `llm_client.py:76` |
| `EXCHANGE` | `"binance"` | str | `config.py:25`, `deps.py:83` |
| `EXCHANGE_API_KEY` / `EXCHANGE_API_SECRET` | `None` | str | `config.py:26-27`, `deps.py:85-86` |
| `EXCHANGE_TESTNET` | `true` | bool | `config.py:28`, `deps.py:84` |
| `EXCHANGE_DRY_RUN` | **obrigatório (sem default)** | bool; unset → `RuntimeError` | `exchange_client.py:41-48`, `routes/config.py:58` |
| `ORDER_ROUTING` | `"paper"` | paper\|live | `exchange_client.py:62-64` |
| `DRY_RUN_BASE_PRICE` | `"50000"` | float | `exchange_client.py:50` |
| `DRY_RUN_BASE_PRICES` | `""` | CSV `PAIR=PRICE` | `exchange_client.py:53` |
| `MARKET_PAIRS` | `BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT` | CSV | `pairs.py:21` |
| `SYMBOLS` | (unset → `BTC/USDT`) | CSV (subset de MARKET_PAIRS) | `orchestrator_loop.py:50` |
| `INITIAL_CAPITAL` | `10000` | float | `config.py:31`, `deps.py:24`, `hitl/orders.py:392` |
| `MAX_POSITION_SIZE_PCT` | `5.0` | float | `config.py:32`, `risk_agent.py:20`, `guardrails.py:13` |
| `STOP_LOSS_PCT` | `3.0` | float | `config.py:33`, `risk_agent.py:21` |
| `MAX_DAILY_LOSS_PCT` | `5.0` | float | `config.py:34`, `risk_agent.py:22` (**X** no RiskAgent) |
| `MAX_CONCURRENT_POSITIONS` | `3` | int | `config.py:35` |
| `AUTONOMY_LEVEL` | `1` (config) / `2` (hitl) | int (0-3 no hitl) | `config.py:38`, `hitl/config.py:64` |
| `HITL_APPROVAL_REQUIRED` | `true` | bool | `config.py:39` |
| `ORCHESTRATOR_INTERVAL_SECONDS` | `60` | int [10,3600] | `orchestrator_loop.py:74`, `routes/config.py:60` |
| `DATABASE_URL` | `sqlite:///./data/trading.db` | str; `postgres*`→PG | `config.py:42`, `db.py:35` |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | str | `config.py:48` |
| `PROMETHEUS_PORT` | `9090` | int | `config.py:54` |
| `LEDGER_DIR` | `.buildtovalue/ledger` | path | `config.py:89`, `ledger.py:30`, `alerts.py:57` |
| `JOURNAL_PATH` | `data/trade_journal.json` | path | `journal/trade_journal.py:106` |
| `API_KEYS` | `""` (fail-open) | CSV allowlist | `api/main.py:53` |
| `CORS_ORIGINS` | `"*"` | CSV | `api/main.py:72,218` |
| `SENTRY_DSN` / `SENTRY_TRACES_SAMPLE_RATE` | `""` / `0.0` | str/float | `api/main.py:185,196` |
| `REDIS_URL` | (unset → in-memory) | str | `ratelimit.py:88` |
| `API_URL` / `API_KEY` / `REFRESH_INTERVAL` (dashboard) | `http://localhost:8000` / `""` / `5` | str/str/int | `dashboard/app.py:16-18` |
| Infra: `POSTGRES_DB/USER/PASSWORD`, `GF_SECURITY_ADMIN_USER/PASSWORD` | (compose) | str | `docker-compose.yml` |

> Constantes de caminho (`config.py:85-90`): `PROJECT_ROOT` (=`src/`), `DATA_DIR`, `LOGS_DIR`, `LEDGER_DIR`, `CONFIG_DIR`. Settings inner `Config`: `env_file=".env"`, `extra="ignore"`.

### 1.2 Configuração YAML (dados de política)

**`config/strategies/risk_params.yaml`** — lido por `routes/risk.py:28`. Seções e chaves-dado:
- `position_limits`: `max_position_size_pct 5.0`, `min_position_size_pct 1.0`, `max_concurrent_positions 3`, `max_exposure_per_asset 15.0`
- `stop_loss`: `mandatory true`, `default_pct 3.0`, `max_allowed_pct 5.0`, `trailing_enabled false`
- `take_profit`: `mandatory false`, `default_pct 9.0`, `min_risk_reward_ratio 1.5`
- `loss_limits`: `max_loss_per_trade_pct 3.0`, `max_daily_loss_pct 5.0`, `max_weekly_loss_pct 10.0`, `max_monthly_loss_pct 15.0`; `circuit_breaker{enabled, trigger_daily_loss_pct 4.0, trigger_consecutive_losses 3, cooldown_period_hours 24}`
- `diversification`, `leverage{allowed false, max 1.0}`, `order_types{allowed[limit], prohibited[market,stop_market], slippage{max 0.5, simulated_in_paper 0.2}}`
- `market_conditions{volatility.max 80, liquidity.min_24h_volume_usd 1e8, trend.min_indicators_aligned 2}`
- `capital{initial 10000, reserve_pct 20, max_deployed_pct 80}`, `performance_targets{sharpe 1.5, max_drawdown 15, win_rate 55, profit_factor 1.8}`
- `signal_validation{min_confidence 0.6, filters[volume_surge,spread_check,momentum_confirmation]}`, `fees{exchange_fee_pct 0.1, slippage 0.2, break_even 0.6}`
- `strategies{dca_optimized(size 2.0,entries 3,spacing 1.0), grid_trading(disabled), momentum(disabled)}`, `mode{current paper_trading, transition_criteria...}`

**`config/agents/constitution.yaml`** (v6.1): `agents.{strategy(autonomy 2, chain_of_thought),risk(autonomy 3, reflection),execution(autonomy 1, react)}` cada com role/goals/capabilities/constraints/tools/performance_targets; `collaboration.flow: strategy→risk→hitl→execution→ledger`; `global_guardrails.{security,risk_management,operational}`; `audit.ledger_path .buildtovalue/ledger/trades.jsonl`.

**`config/prometheus.yml`**: `scrape_interval 15s`, job `app` → `app:8000`.
**`metrics.yaml` / `metrics-advanced.yaml`**: catálogos `{metric,target,alert,dashboard}` (technical/business/ai_squad/agent). **`config/prompts/advanced_agent_prompts.py`**: `AGENT_PROMPTS: dict[str,str]` com 4 prompts (`architect_with_cot`, `developer_with_react`, `auditor_with_reflection`, `consensus_facilitator`).

### 1.3 Dados de entrada externos (runtime)
- **Exchange (CCXT)** — OHLCV `[ts_ms,o,h,l,c,v]`, ticker, order book, balance, ordens (ver §4.8 `exchange_client`). Em dry-run vêm de `synthetic_market` (determinístico).
- **LLM** — entrada `(system, user)` strings; saída `str` ou JSON `{confidence, thesis}` (Strategy) / `{note, hidden_risk}` (Risk).
- **HTTP** — corpo/query/headers das rotas `/v1/*` (ver §5).

---

## 2. Dados persistidos — bancos e arquivos

### 2.1 Tabelas SQLite/Postgres (migrations)

| Tabela | Colunas (tipo · constraint) | Índices | Origem |
|---|---|---|---|
| **orders** (`001`) | `id TEXT PK`, `pair TEXT NN`, `side TEXT NN CHECK(buy\|sell)`, `quantity REAL NN >0`, `price REAL NN >0`, `strategy TEXT`, `agent_id TEXT`, `confidence REAL`, `reason TEXT`, `critical INT NN=0`, `position_size_pct REAL`, `stop_loss REAL`, `take_profit REAL`, `status TEXT NN='pending' CHECK(pending\|approved\|rejected\|cancelled\|filled)`, `operator_note TEXT`, `operator_id TEXT`, `auto_approved INT NN=0`, `created_at TEXT NN`, `resolved_at TEXT`, `filled_at TEXT` | `status`, `created_at` | HITL bridge |
| **cycle_events** (`001`) | `id INT PK AUTOINC`, `agent_id TEXT NN`, `cycled_at TEXT NN` | `(agent_id,cycled_at)` | contador de ciclos |
| **journal_entries** (`002`) | `id INT PK AUTOINC`, `setup TEXT NN`, `emotion_before INT NN CHECK 1..10`, `emotion_after INT CHECK 1..10`, `stop_defined INT NN=0`, `plan_followed INT NN=0`, `pnl_pct REAL`, `note TEXT`, `created_at TEXT NN=now` | `created_at`, `emotion_before` | diário |
| **backtest_jobs** (`003`) | `id TEXT PK`, `status TEXT NN CHECK(running\|done\|error)`, `config_json TEXT`, `result_json TEXT`, `error TEXT`, `created_at TEXT NN`, `completed_at TEXT` | `status`, `created_at` | jobs async |
| **open_positions** (`004`) | `order_id TEXT PK`, `symbol TEXT NN`, `side TEXT NN`, `entry_price REAL NN`, `quantity REAL NN`, `stop_loss REAL`, `take_profit REAL`, `opened_at TEXT NN` | `symbol` | book paper |
| **circuit_breaker_state** (`004`) | `id INT PK CHECK(id=1)` (singleton), `tripped_at REAL`, `consecutive_losses INT NN=0`, `daily_loss_pct REAL NN=0.0` | — | breaker |
| **ledger_events** (criada em `ledger.py:48`) | `id {autoincrement_pk}`, `timestamp TEXT NN`, `event_type TEXT NN`, `data TEXT NN` (JSON) | `event_type` | event store |
| **schema_migrations** (`db.py:205`) | `version TEXT PK`, `applied_at TEXT NN` | — | migrations |

> **Sem foreign keys** entre tabelas (design de coordenação cross-process). `db.py` abstrai `connection()`; PG traduz `?`→`%s` (`db.py:102`); `_Row`/`_PgConn` adaptam PG à API sqlite3.

### 2.2 Event store — payloads do `ledger_events.data` (JSON)

Cada `log_*` de `TradingLedger` grava `(timestamp, event_type, data)`:

| Método | `event_type` | chaves de `data` | linha |
|---|---|---|---|
| `log_signal(agent,signal)` | `signal_generated` | `agent`, `signal`(dict) | `ledger.py:74` |
| `log_validation(agent,validation)` | `risk_validation` | `agent`, `validation`(dict) | `:78` |
| `log_execution(agent,execution)` | `order_executed` | `agent`, `execution`(dict) | `:82` |
| `log_hitl_approval(approved,order,user)` | `hitl_approval` | `approved`(bool), `order`(dict), `user`(str="default") | `:86` |
| `log_process_event(case_id,activity,actor,attributes)` | `process_event` | `case_id`, `activity`, `actor`, `attributes`(dict) | `:90` |
| `log_fill(...)` | `order_fill` | `order_id`, `symbol`, `side`(lower), `price`, `quantity`, `notional`(=p·q), `fee`, `strategy`, `agent` | `:116` |
| `log_position_closed(...)` | `position_closed` | `order_id`, `symbol`, `side`(lower), `entry_price`, `exit_price`, `quantity`, `fee`, `gross_pnl`, `pnl`(=gross−fee), `pnl_pct`, `opened_at` | `:149` |
| `log_decision(event_type,data)` | arbitrário | ex.: CircuitBreaker → `circuit_breaker_tripped`/`_reset` com `{reason}` | `:60` |

**Atividades XES** (via `log_process_event`): `agent_cycle_started/completed/failed` (loop), `order_submitted/approved/rejected/cancelled/filled` (OrderStore), `hitl_level_changed` (HITLConfigStore).

### 2.3 Arquivos append-only (JSONL/JSON)

| Arquivo | Registro (chaves) | Escrito por |
|---|---|---|
| `trades.jsonl` (legado) | — (histórico) | `ledger.py` |
| `alerts.jsonl` | `severity, type, message, agent_id, pair, auto_action, id, occurred_at` | `AlertStore.append` (`alerts.py`) |
| `agent_memories.jsonl` | `agent, decision`(dict), `timestamp` | `AgentMemorySystem.remember_decision` (`agent_memory.py:39`) |
| `trade_journal.json` | `{order_id: asdict(TradeEntry)}` (objeto único) | `TradeJournal._save` (`trade_journal.py:211`) |
| `ab_tests.jsonl` | `{timestamp, winner, scores, statistical_significance}` — **`str()` repr, não JSON** | `ab_testing.py:60` |
| `loop_heartbeat.json` | `{ts, cycle_id}` | `heartbeat.write_heartbeat` |

---

## 3. Estruturas de dados canônicas em trânsito

Estes são os **dicts que fluem entre módulos** — o dado "vivo" do sistema. Chaves exatas e origem.

### 3.1 `task` (entrada de cada `agent.execute`)
- **Strategy** `{symbol, timeframe}` — `squad_orchestrator.py:207`
- **Risk** `{signal, portfolio:{available_capital, capital_base}}` — `:241`
- **Execution** `{signal, human_approved, quantity}` — `:272`

### 3.2 `analysis` (StrategyAgent._analyze_market → strategy_agent.py:160)
`symbol, timeframe, current_price, trend`(bullish\|bearish\|None)`, regime, eligible_strategies:list[str], indicators:TechnicalIndicators, support_resistance, fibonacci_levels:dict, volume_profile, rsi_divergence, macd_divergence, market_extreme, stub_used:bool, _ohlcv:list` (I; `_ohlcv` removido antes de logar). Versão stub (`:446`) espelha as chaves com valores fixos (`regime="sideways"`, `eligible_strategies=["grid","dca"]`).

### 3.3 `signal` (StrategyAgent._generate_signal → strategy_agent.py:218) — **o dado central do sistema**
`action`(BUY\|SELL\|HOLD)`, entry_price, stop_loss, take_profit, position_size_pct`(default 2.0)`, strategy, regime, market_context:{atr,bb_middle,volume_ratio}|None`. `symbol` é adicionado depois pelo orquestrador via `setdefault` (`:214`); `reason` só existe nos caminhos HOLD.

### 3.4 `market_data` — formato unificado (ver nota)
- **Nested** (StrategyAgent e backtest) — `_build_market_data` (`strategy_agent.py:383`): `symbol, current_price, trend, regime, rsi, macd_histogram, at_bollinger_lower, ma_20, ma_50, volume_24h, avg_volume, indicators:TechnicalIndicators, support_resistance, volume_profile, _raw_ohlcv`
- **Backtest** — `engine._build_market_data`: 🟢 **desde Onda 2** computa `indicators:TechnicalIndicators` real + `regime` (guarda de warmup `WARMUP_CANDLES=50`), mantendo os campos flat (`rsi/ma_20/ma_50/...`) que DCA lê. Fallback a placeholders só se os indicadores não puderem ser computados (janela curta / numpy ausente em CI mínima). Antes emitia flat com `rsi=50`/`indicators` ausente — o que deixava Grid/MeanReversion inertes no backtest.

### 3.5 Resultados dos agentes
- **strategy_result** (`strategy_agent.py:89`): `success, agent, signal, confidence, analysis, llm_used, llm_thesis, stub_used`
- **risk_result** (`risk_agent.py:64`): `success, agent, approved, validation:{approved,issues,warnings,confidence,[requires_review],refined,reflection_applied}, confidence`
- **execution_result** (`execution_agent.py:50`): `success, agent, order_id, executed_price, fee, confidence`
- **analyze_and_trade** (`squad_orchestrator.py:297`): `success, order_id, signal, confidence` — ou `{success:False, reason, ...}` nos caminhos de rejeição
- **run_cycle** (`orchestrator_loop.py:149`): `{cycle_id, ran:list[str], failures:list[{agent_id,error}]}`

### 3.6 `Order` (dataclass HITL — hitl/orders.py:48)
`pair, side, quantity, price, strategy, agent_id, confidence, reason, critical=False, position_size_pct=0.0, stop_loss=None, take_profit=None, status=pending, operator_note=None, operator_id=None, auto_approved=False, id="ord_"+hex8, created_at, resolved_at=None, filled_at=None`; property `notional=price*quantity`; `guardrail_view()→{position_size_pct,action=side.upper(),entry_price=price,stop_loss,take_profit}`.

### 3.7 `_open_positions[order_id]` (book paper — squad_orchestrator.py:374)
`{symbol, side(lower), entry_price, quantity, stop_loss|None, take_profit|None, opened_at(iso)}` — espelhado em SQLite via `PositionStore`.

---

## 4. Catálogo por módulo — backend Python

> Formato: por arquivo/classe, os dados com marca **E/S/I/P/X**. Atributos de estado listados no `__init__`.

### 4.1 `src/agents/`

**`base_agent.py` — BaseAgent** (`:17`)
- **I** `self.agent_type`(:21), `self.agent_id`(uuid,:22), `self.created_at`(:23), `self.confidence_threshold=0.6`(:24), `self.memory`(:29), `self.tools=[]`(:35)
- `log_decision` → **I/S** `entry={timestamp,agent,agent_id,decision}`(:48) → grava em memory + retorna

**`strategy_agent.py` — StrategyAgent** (detalhado em §3.2–3.5)
- **I** `_sr_detector`, `_div_detector`, `_strategy_cache:dict`(key→instância), `_llm`
- `_llm_assess` **I** `context`{symbol,regime,trend,action,strategy,entry_price,stop_loss,take_profit,deterministic_confidence,rsi,macd_hist,bb_percent,volume_ratio}(:344) → LLM → `(blended,thesis)`
- `_stub_analysis` **I** `stub_ind` TechnicalIndicators hardcoded (current_price=50000, rsi=45, bb_percent=0.25, atr=50, volume_ratio=1.2...)(:434)
- confiança: blend `0.6·strategy + 0.4·agent` (:57), com LLM `0.5/0.5` (:373), clamp [0.10,0.95]

**`risk_agent.py` — RiskAgent**
- **I** `guardrails=GuardrailSystem()`(:18), `max_position_size_pct`(:20), `stop_loss_pct`(:21), **X** `max_daily_loss_pct`(:22 — nunca lido), `_llm`
- `_validate_signal` **E** signal.{position_size_pct,entry_price,stop_loss}, portfolio.{available_capital,capital_base} → **S** `{approved,issues,warnings,confidence}`(:119)
- `_reflect_on_validation` **S** `{missed_anything,too_strict,suggestions,[llm_note]}`
- `_refine_validation` **S** `final` = validation + `{[requires_review],refined,reflection_applied}`

**`execution_agent.py` — ExecutionAgent**
- **I** `exchange`, `paper_trading=True`
- `_simulate_order` **E** signal.{symbol,action}, quantity → exchange.create_order → **S** `{success,order_id,executed_price,fee,status,message}`(:112)

**`registry.py`**
- **I** `AGENT_REGISTRY` (5 AgentInfo: strategy/risk/execution implemented, recovery/exploration stub) (:38)
- **I** `AGENT_PARAMS` catálogo estático por agente (confidence_threshold, tools, reasoning_pattern, autonomy_level, e p/ risk: max_position_size_pct/stop_loss_pct/max_daily_loss_pct/min_risk_reward_ratio) (:52)
- **I** `self._cycles:dict`, `self._last_action:dict`, `self._cycles_date` — **P** grava `cycle_events`
- `status()` **S** `{id,domain,implemented,description,status,cycles,last_action_at,params}`

**`behavioral_guard.py`** — constantes REVENGE_LOSS_STREAK=2, REVENGE_SIZE_MULTIPLIER=1.50, EUPHORIA_WIN_STREAK=3, EUPHORIA_SIZE_MULTIPLIER=1.20, OVERCONFIDENCE_MARGIN=0.15. `BehavioralAlert{detected,kind,message,action,recommended_size_multiplier,recommended_confidence_cap}`. `check` **E** new_trade.{position_size_pct,confidence}, trade_history[].{position_size_pct,pnl}, win_rate.

**Agentes de engenharia** (não no pipeline de trading; executados por `UnifiedOrchestrator`):
- `architect_agent` **S** `{reasoning{problem_analysis,constraints,applicable_patterns,trade_offs,recommendation,confidence=0.85,reasoning_steps},plan{goal,architecture,components,patterns,risks,mitigations},adr:str}`
- `developer_agent` **I** `history[{iteration,thought,action,observation}]`, max_iterations=5 → **S** `{status,history,final_output,confidence}`
- `auditor_agent` **S** audit `{issues,warnings,passed,confidence}`; validate_results `{approved,confidence,issues,agent_scores}`
- `designer_agent` **S** `{pattern,theme,components,colors{primary,secondary,background},typography,responsive,accessibility,confidence}`
- `ops_agent` **S** deploy `{strategy,stages,rollback_plan,health_checks,scaling{min_instances=2,max_instances=10,target_cpu=70}}`, monitoring `{metrics,alerts,dashboards,logging}`
- `supervisor_agent` `SupervisorAgent{orchestrator:Agent, specialists:list[Agent]}` → `run(task:str)→str`
- `recovery_agent`/`exploration_agent` dataclasses `{remediation_tool}`/`{scanner_tool}` → `arun→str`

### 4.2 `src/orchestration/`

**`squad_orchestrator.py`**
- **CircuitBreaker** — constantes DAILY_LOSS_LIMIT_PCT=4.0, CONSECUTIVE_LOSS_LIMIT=3, COOLDOWN_SECONDS=86400. **I/P** `_tripped_at`, `_consecutive_losses`, `_daily_loss_pct` (persistidos em `circuit_breaker_state`). `record_trade_result(pnl_pct)` acumula; `_trip/_reset` gravam ledger `circuit_breaker_tripped/_reset{reason}`.
- **SquadOrchestrator** — **I** agentes, ledger, circuit_breaker, `_last_order_ref`, `_open_positions`, `_positions` (§3.7). Pipeline `analyze_and_trade` (§3.5, §7). `_available_capital = initial + _realized_pnl − open_notional`. `_position_quantity = (capital·size_pct/100)/price`. Emite `Alert` type=`data_fallback`/`risk_rejection` (severity high).

**`orchestrator_loop.py`** — constantes MIN/MAX/DEFAULT_INTERVAL=10/3600/60. `run_cycle` **I** `cycle_id`, `ran_agents`, `failures`; grava XES `agent_cycle_started/completed/failed`. `from_env` monta ExchangeClient/ledger/registry/OrderStore/handler/SquadOrchestrator. `AgentExecutionError.agent_id`.

**`position_store.py`** — `PositionStore.load_all()→{order_id:{symbol,side,entry_price,quantity,stop_loss,take_profit,opened_at}}`; `save/load_circuit_state→{tripped_at,consecutive_losses,daily_loss_pct}`.

**`heartbeat.py`** — `{ts,cycle_id}` (HEARTBEAT_FILENAME="loop_heartbeat.json").

**`unified_orchestrator.py`** (squad de engenharia, fora do trading) — **I** planner/router/consensus/parallel/evaluator/autonomy/memory + **X** `sandbox`, `chain_manager` (criados, nunca usados). `execute_complex_task` **S** `{success,task_id,plan,consensus,results,validation,confidence}`.

### 4.3 `src/strategies/`
- `STRATEGY_REGISTRY = {"dca":DCA, "grid":Grid, "mean_reversion":MeanReversion}` (`__init__.py:17`)
- **MeanReversion** params `{rsi_oversold=30, rsi_overbought=70, risk_reward=2.0, atr_mult=2.0}`. **E** `market_data.{indicators(rsi,bb_lower/upper/middle,atr,volume_ratio,stochastic_k),current_price,regime}`. **S** `{action,direction,entry,stop_loss,take_profit,position_size_pct=2.0,confidence,reason}` ou HOLD `{action,confidence=0.05,reason}`.
- **Grid** params `{grid_levels=10,grid_spacing_pct,total_size_pct,size_per_level}`. **E** `indicators.{ema_fast,ema_slow,atr,bb_middle,volume_ratio}, volume_profile.poc, regime`. **S** `{action,direction,entry,stop_loss,take_profit=None,position_size_pct,total_position_size_pct,grid_levels:{buy:[],sell:[]},confidence,reason}`.
- **DCA** params `{position_size_pct=2.0,num_entries=3,spacing_pct=1.0,stop_loss_pct=3.0,rsi_oversold=35,min_volume_ratio=0.8}`. **E** flat `market_data.{symbol,current_price,ma_20,ma_50,rsi,macd_histogram,at_bollinger_lower,volume_24h,avg_volume}`. **S** `{action:"DCA_ENTRY"|"WAIT",signal:{symbol,strategy,action,entries:[{entry_number,price,size_pct}],avg_entry_price,stop_loss,take_profit,total_position_size_pct,risk_reward_ratio=3.0,timestamp},confidence,reasoning}`.

### 4.4 `src/analysis/` (dataclasses = DTOs de análise)
- **TechnicalIndicators** (20 campos `float|None`): sma_20/50/200, ema_fast, ema_slow, rsi, stochastic_k/d, macd_line/signal/hist, bb_upper/middle/lower, bb_percent, atr, volume_ratio, obv, current_price (`indicators.py:18`). OHLCV in = `[ts_ms,o,h,l,c,v]`. `MIN_CANDLES=50`.
- **DivergenceResult** `{detected,kind,description}`; **TrendAlignment** `{primary,secondary,minor,aligned,direction}`; MultiTimeframeTrend TIMEFRAMES `{primary:1w,secondary:1d,minor:1h}`.
- **SRLevel** `{price,kind,strength,last_touch}`; **SRLevels** `{support,resistance,zones:[SRLevel]}`; `fibonacci_levels→{"0.0%".."100.0%":price}`.
- **VolumeProfileResult** `{poc,value_area_high,value_area_low,low_volume_nodes:[]}`.
- **PatternResult** `{pattern,confidence,direction,target_price,candle_index,description}`.
- **regime_detector** (funções): `detect_regime→"unknown"|"chaotic"|"strong_uptrend"|"strong_downtrend"|"sideways"`; `_REGIME_STRATEGY_MAP{strong_uptrend:[dca],strong_downtrend:[],sideways:[grid,dca],chaotic:[],unknown:[dca]}`; `detect_market_extreme→"EUFORIA…"|"PÂNICO…"|None`.

### 4.5 `src/backtest/`
- **BacktestTrade** `{candle_index,action,entry_price,exit_price,position_size_pct,pnl_usdt,pnl_pct,stop_loss,take_profit,exit_reason}`.
- **BacktestResult** `{total_trades,win_rate,total_pnl_usdt,total_pnl_pct,max_drawdown_pct,sharpe_ratio,profit_factor,avg_win_pct,avg_loss_pct,trades:[BacktestTrade]}` + prop `expectancy`. Constantes commission 0.001, slippage 5bps, warmup 50.
- **WindowResult**/`WalkForwardResult` (validação walk-forward; MAX_SHARPE_DEVIATION=0.30). **MonteCarloResult** `{n_simulations,median/p5/p95_pnl_pct,max_simulated_drawdown,pct_profitable,rejected}`.
- `_build_market_data` (desde Onda 2) computa `indicators` real + `regime` (§3.4) → estratégias dirigidas por indicadores (Grid/MeanReversion) exercitam o mesmo caminho que o live, não só DCA.

### 4.6 `src/risk/`
- **KellyCriterion** `{win_rate,avg_win_pct,avg_loss_pct,capital=10000,n_trades}` → `full_kelly()|None` (min 30 trades), `fractional_kelly(0.25)` clamp [0.5,5.0], `ruin_risk()`. Constantes KELLY_FRACTION=0.25, MIN/MAX_POSITION_PCT=0.5/5.0, MIN_SAMPLE_FOR_KELLY=30.
- **PositionSizer** `compute(entry,stop)→size%` clamp [0.5,5.0].
- **CapitalProtections** `check(daily,weekly,monthly)→ProtectionResult{status:DrawdownStatus,message,size_multiplier(1.0/0.5/0.0),can_trade}`. Limites DAILY=3.0/WEEKLY=6.0/MONTHLY=15.0/WARN=2.4. **DrawdownStatus** = OK/WARN/DAILY_PAUSE/WEEKLY_REDUCED/MONTHLY_SUSPEND.

### 4.7 `src/safety/`
- **GuardrailSystem** `validate_order(order)→(bool,list[str])`. **E** order.{position_size_pct,stop_loss,entry_price,action,take_profit,market_context:{atr,bb_middle,volume_ratio}}. Regras: position≤max, stop obrigatório e do lado certo, risk_reward≥2.5, market atr/bb_middle≤0.10 e volume_ratio≥0.3. `alert_sink:Callable[[str],None]`.
- **SecurityConfig** (dataclass) `{MAX_POSITION_SIZE_PCT=5.0,MAX_STOP_LOSS_PCT=3.0,MAX_DAILY_LOSS_PCT=5.0,MAX_CONCURRENT_POSITIONS=3,MAX_EXECUTION_TIME_SECONDS=30,FORBIDDEN_PATTERNS[leverage.*10x,margin.*call,liquidation,all.*in,100%.*position]}`; ClassVars FORBIDDEN_TOOL_NAMES(rm,delete_resource,format_disk,drop_database), SENSITIVE_PARAM_PATTERNS(rm -rf,drop table,delete from,format), ALLOWED_EXCHANGES{binance,coinbase,kraken}, HIGH_RISK_ACTIONS. `validate_order` **E** order.{position_size_pct,notes,exchange}; `validate_tool_call(tool_name,params)`.

### 4.8 `src/core/` (resumo — detalhe completo em §1, §2)
- **config.Settings** (23 campos env, §1.1); funções `get_risk_params/get_resource_limits/get_autonomy_config`.
- **db** `connection()`, `upsert`, `init_db`, `_Row`, `_PgConn` (§2.1).
- **ledger.TradingLedger** — event store (§2.2); read `_row_to_entry→{timestamp,event_type,data}`.
- **metrics.PortfolioMetrics** (14 campos §5) derivado de `position_closed`+`order_fill`. `_PERIOD_DAYS{1d,7d,30d,90d,all}`.
- **exchange_client.ExchangeClient** — `fetch_ticker→{symbol,last,close,bid,ask,timestamp,info}`, `fetch_ohlcv→[[ts,o,h,l,c,v]]`, `fetch_order_book→{bids,asks}`, `fetch_balance→{USDT:{free,used,total},BTC:{...}}`, `create_order/_create_paper_order→{id="PAPER_"+hex8,symbol,type,side,amount,price,average,filled,remaining,status,fee:{cost,currency},timestamp,datetime,info}`. `simulated_orders:dict`. Slippage 0.002, fee 0.001.
- **alerts** — Alert `{severity,type,message,agent_id,pair,auto_action,id,occurred_at}`; AlertStore JSONL; AlertBus fila `asyncio.Queue(maxsize=100)`; `make_guardrail_sink`. SEVERITIES=(low,medium,high,critical).
- **llm_client.LLMClient** `reason(system,user)→str?`, `reason_json→dict?`; `_DEFAULT_MODELS{google:gemini-1.5-flash,openai:gpt-4o-mini,anthropic:claude-haiku-4-5-...}`.
- **ratelimit** InMemory `_buckets:dict[str,list[float]]` / Redis `INCR+pexpire` (key `ns:key`); janela 60s.
- **pairs** DEFAULT_PAIRS; `parse_pairs`/`allowed_pairs`/`is_allowed`.
- **synthetic_market** `_DEFAULT_BASES{ETH:3000,SOL:150,BNB:600,XRP:0.5}`; `synthetic_ticker/ohlcv/order_book`.
- **request_context** `request_id_var:ContextVar(default="-")`; RequestIdLogFilter.
- **safe_agent_base** — Plan/PlanCreation/AgentExecution dataclasses; GuardrailSuite + 4 guardrails; MemoryManager.

### 4.9 `src/hitl/`
- **OrderStore** (§3.6, §5.6): `submit/resolve/mark_filled/cancel/wait_for_decision`. Auto-approve quando `notional≤threshold & !critical & risk_ok`. `make_approval_handler` mapeia signal→Order (§7).
- **config.HITLConfigStore** `snapshot()→{current_level,threshold_usdt,level_description,min_level,max_level,pending_orders_count,human_approved_today,human_rejected_today,last_changed_at,last_changed_by,levels:[{level,threshold_usdt,description}]}`. AUTONOMY_LEVELS {0:0.0,1:500,2:1000,3:5000}, DEFAULT=2.
- **progressive_autonomy.ProgressiveAutonomyManager** (não ligado às rotas): `autonomy_levels{0..3}`, `agent_trust_scores:dict`, `action_history:[{timestamp,agent,action,success,trust_score,autonomy_level}]`; score +0.02/−0.1; result `{approved,feedback,modifications}`.

### 4.10 `src/memory/`, `src/journal/`, `src/tools/`, `src/evaluation/`, misc
- **AgentMemorySystem** — **X** `short_term:dict` (nunca escrito); episodic JSONL `{agent,decision,timestamp}`; Chroma opcional. `recall/recall_similar`.
- **IntelligentForgetting** — `MemoryStore.data:{key:{relevance}}`; remove relevance<0.1.
- **TradeJournal** — TradeEntry (identidade+setup+psicologia+resultado, §4 detalhe); JournalStats (9 campos); JSON `{order_id:asdict}`.
- **MCPToolRegistry** — `tools:dict[str,callable]`; core tools `analyze_code_quality→{file,complexity,coverage,issues}`, `generate_tests→str`, `optimize_performance→{suggestions,estimated_gain}`.
- **rag_tool** VectorDBClient `_collection_name="btf-default"`; RAGTool.retrieve.
- **sandbox** DockerSandbox `{image=python:3.11-slim,network_disabled=True}`; SecureToolSandbox `{docker_sandbox,execution_timeout=30,` **X** `memory_limit_mb=512,` **X** `cpu_quota=0.5,allow_unsandboxed=False}`; result `{tool,output|params,sandboxed,[message]}`.
- **evaluation** — `continuous_eval.ContinuousEvaluator` (**X** `baseline`) `evaluate_trajectory→{task_completion,efficiency,safety}` (lê trajectory.{completed,resource_usage,guardrail_violations}); `continuous_evaluator.ContinuousEvaluator` (dataclass) metrics `{task_success_rate,average_confidence,` **X** `user_satisfaction,error_rate,response_time_p95}`; `ab_testing` result `{winner,scores{A,B},statistical_significance}`.
- **consensus.WeightedConsensusEngine** `agent_weights{architect,developer,auditor,designer,ops:{domínio:peso}}`; `reach_consensus→{decision,consensus_strength,decision_maker,dissenting_opinions:[{agent,score}]}`.
- **routing.LearningRouter** `route_performance{route_hash:{attempts,successes,total_latency,success_rate,avg_latency}}`; `smart_route→request["preferred_route"]|"default"`.
- **planning** — `hierarchical_planner` plan `{goal,steps,alternatives,confidence}`; `adaptive_planner` plan `{plan_id,task_id,goal,steps:[{step,action,description,estimated_time,dependencies,can_fail}],estimated_duration,created_at,adaptive,confidence}`; `adaptive_replanner` (dup) `{plan,result,attempts}`.
- **chains.ChainStep** `{name,execute}` / ResilientPromptChain `{steps,max_retries=3}`. **parallel.ParallelResourceManager** `limits{max_concurrent:5}`.
- **protocols.MCPServer** card `{name,skills,endpoint}`, handle_request(type discover|execute). **protocols.SquadOrchestrator** `delegate_task→{plan,implementation}`.
- **utils.observability** SpanRecord `{operation,metadata,start_time,reasoning_log,end_time}`; `export_trajectory→{trace_id,spans:[...]}`. **utils.MemoryStore** key/value. **tool_utils.wrap_sync_tool**.
- **main.py** `MemoryStore.set("usuario","João")`; **orchestrator.py** AgentOrchestrator (base_agent+evaluator+rag_tool+observer+mcp_server) `execute_with_monitoring→(AgentExecution,evaluation)`.

---

## 5. Dados da camada API

### 5.1 Middleware (dados lidos/escritos, em ordem de execução)
| Middleware | Dado | `arquivo:linha` |
|---|---|---|
| RequestId | lê/escreve header `X-Request-ID`; grava `request_id_var` | `request_id.py:23-29` |
| Prometheus | Counter `http_requests_total{method,path,status}`, Histogram `http_request_duration_seconds{method,path}`; gauges de domínio `criptotrade_{open_positions,total_trades,portfolio_value_usdt,realized_pnl_usdt,win_rate,sharpe_ratio}` | `observability.py:18-89` |
| RateLimit | `request.client.host` → key `ip:w|r`; WRITE=30/READ=200/min; 429 `{error,message,retry_after,docs}` | `main.py:128-164` |
| SecurityHeaders | escreve CSP, X-Frame-Options=DENY, X-Content-Type-Options=nosniff, Referrer-Policy, HSTS max-age=300, X-XSS-Protection=0 | `main.py:109-125` |
| CORS | `CORS_ORIGINS`; métodos GET,POST,PATCH; headers X-API-Key,Content-Type | `main.py:216` |
| APIKey | lê header `X-API-Key`; PUBLIC_PATHS isentos; 401 `{error,message,docs}` | `main.py:84-106` |

**Handlers de exceção**: 422 `{error:validation_error,message,field,docs}`; 404 `{error:not_found,message,docs}`; 500 `{error:internal_error,message,docs}` (`main.py:265-313`).

### 5.2 Envelope e DTOs (schemas.py) — contrato de saída/entrada
- **APIResponse[T]** `{data:T, meta:Meta?, links:Links?(alias _links)}`; **Meta** `{total,page=1,per_page=20,timestamp}`; **Links** `{self,related?}`; **ErrorResponse** `{error,message,field?,docs="/v1/docs"}`.
- **PortfolioMetricsOut** (14): sharpe_ratio?, win_rate?, max_drawdown, profit_factor?, total_trades, open_positions, portfolio_value_usdt, pnl_period_usdt, pnl_period_pct, exposure_pct, initial_capital_usdt, period, calculated_at, has_data.
- **OrderCreate** (E): pair(regex `^[A-Z]{2,10}/[A-Z]{2,10}$`), side(OrderSide), quantity(>0), price(>0), strategy(min1), agent_id(min1), confidence(0-1), reason(min10), critical=False, position_size_pct(0-100], stop_loss(>0, **obrigatório**), take_profit?(>0).
- **OrderDecisionPatch** (E): decision(`^(approve|reject)$`), operator_note?(**obrigatório em reject**), operator="operator".
- **OrderOut** (S): id,pair,side,quantity,price,notional,status,strategy,agent_id,confidence,reason,critical,auto_approved,operator_note?,operator_id?,position_size_pct?,stop_loss?,take_profit?,rr?,created_at,resolved_at?,filled_at?.
- **HITLConfigOut**, **AutonomyLevelOut/Patch**, **AgentStatusOut/ConfigOut**, **ProcessEventOut**{case_id,activity,actor,timestamp,attributes}, **AlertOut**, **ClosedTradeOut**, **EquityPoint**{t,equity,drawdown}.
- Mercado: **CandleOut**{t,o,h,lo,c,v} (nota: `lo`, não `l`), **TickerOut**, **MacdOut/StochOut/BollingerOut**, **IndicatorsOut** (rsi,macd,stoch,bb,atr,atr_pct,ema9/21,sma20/50/200,obv_trend,volume_ratio,current_price,as_of), **RegimeOut**, **SRLevelOut/LevelsOut**, **VolumeProfileBin/Out**, **PatternOut**, **ConfidenceFactor**, **SignalOut**{action,entry,stop,take_profit,position_size_pct,rr,strategy,confidence,reason,confidence_factors,valid_until,as_of}, **TFSnapshot**, **ConfluenceOut**.
- Risco: **ProtectionOut**{scope,value,limit,status,action}, **CircuitBreakerOut**{status,triggers,cooldown_hours,cooldown_remaining}, **KellyOut** (9 campos), **RiskConfigOut** (14 campos), **RiskConfigPatch** (7 opcionais + confirm).
- Backtest: **BacktestConfigIn**{strategy=dca,pair=BTC/USDT,initial_capital=10000,commission_pct=0.1,slippage_bps=5,monte_carlo_sims=1000}, **BacktestResultOut**, **MonteCarloOut**, **WalkForwardFold/Out**, **BacktestJobOut**{job_id,status,result?,error?}.
- Journal: **JournalEntryCreate**{setup(min3),emotion_before(1-10),emotion_after?(1-10),stop_defined,plan_followed,pnl_pct?,note?}, **JournalEntryOut** (+id,created_at), **EmotionBand**, **JournalMetricsOut**.
- Config: **ConfigOut**{exchange,dry_run,initial_capital,orchestrator_interval_seconds,autonomy_level,app_env}, **ConfigPatch**, **AlertsConfigPatch**{revenge_size_multiplier,euphoria_size_multiplier,overconfidence_margin,risk_of_ruin_alert_pct}.

### 5.3 Rotas `/v1/*` — entradas (query/path/body) → saída
| Rota | Entrada | Saída |
|---|---|---|
| `GET /v1/metrics` | period(1d\|7d\|30d\|90d\|all), symbol? | APIResponse[PortfolioMetricsOut] |
| `GET /v1/metrics/equity` | period, symbol? | List[EquityPoint] |
| `GET/PATCH /v1/hitl/config` | (PATCH) AutonomyLevelPatch; level 3 requer confirm | HITLConfigOut |
| `GET /v1/orders` | status?,pair?,limit(1-500),offset | List[OrderOut] + Meta |
| `POST /v1/orders` | OrderCreate | OrderOut (201 filled/202 pending/422 rejected) |
| `PATCH /v1/orders/{id}/status` | OrderDecisionPatch | OrderOut (404/409) |
| `GET /v1/agents[/{id}][/config]` | path id | AgentStatusOut/ConfigOut (404/501) |
| `GET /v1/process/events` | case_id?,limit(1-1000) | List[ProcessEventOut] |
| `GET /v1/alerts` (SSE) | severity?,replay(0-200) | EventSource {alert,heartbeat} |
| `GET /v1/alerts/history` | severity?,since?,limit,page | List[AlertOut] |
| `GET /v1/market/pairs` | — | List[str] |
| `GET /v1/market/{pair}/{candles,ticker,indicators,regime,levels,volume-profile,patterns,signal,confluence}` | tf,limit,bins? | DTO respectivo (503 se dados indisponíveis) |
| `GET /v1/risk/{protections,circuit-breaker,kelly,config}` · `PATCH /v1/risk/config` | RiskConfigPatch (confirm) | DTOs de risco |
| `POST /v1/backtest/{run,montecarlo,walkforward}` · `GET /v1/backtest/jobs/{id}` | BacktestConfigIn | BacktestJobOut/MonteCarloOut/WalkForwardOut |
| `GET/POST /v1/journal` · `GET /v1/journal/metrics` | JournalEntryCreate | JournalEntryOut / JournalMetricsOut |
| `GET /v1/trades/closed` | symbol?,limit,offset | List[ClosedTradeOut] |
| `GET/PATCH /v1/config` · `PATCH /v1/agents/{id}/config` · `PATCH /v1/alerts/config` | ConfigPatch / params / AlertsConfigPatch | ConfigOut / AgentConfigOut / Dict |

### 5.4 Providers de dependência (`deps.py`, `@lru_cache`)
`get_ledger`→TradingLedger, `get_alert_store/bus`, `get_hitl_store`(wire pending_orders_provider), `get_order_store`(threshold+guardrails+alert_sink), `get_agent_registry(db_path)`, `get_exchange_client`, `get_metrics_calculator`(fresco). `_runtime_overrides:{INITIAL_CAPITAL,ORCHESTRATOR_INTERVAL_SECONDS}` (in-memory, `routes/config.py:24`).

---

## 6. Dados do frontend (React/JS) e contrato TS

### 6.1 `apiClient.js` — CT_API (window.CT_API)
Globais: `window.API_BASE`(default localhost:8000), `window.API_KEY`(header X-API-Key), `window.USE_MOCK_DATA`. `req()` desembrulha `j.data ?? j`. ~40 métodos mapeando 1:1 as rotas `/v1` (getMetrics, getHITL/patchHITL, getOrders/createOrder/decideOrder, getAgents/getAgentConfig/patchAgentConfig, get{Ticker,Candles,Indicators,Regime,Levels,VolumeProfile,Patterns,Signal,Confluence}, get{Protections,CircuitBreaker,Kelly,RiskConfig}/patchRiskConfig, getEquity, getProcessEvents, run{Backtest,MonteCarlo,WalkForward}/getBacktestJob, getJournal/addJournalEntry/getJournalMetrics, getConfig/patchConfig, patchAlertsConfig, getAlertHistory, subscribeAlerts=SSE). Mercado reescreve `BTC/USDT`→`BTC-USDT`.
**CT_PAIR** store: localStorage `'ct.pair'` (default BTC/USDT); CustomEvent `'ct:pair'`. (Market usa `'ct.alerts'` para alertas de preço client-side.)

### 6.2 `data.js` — CT.* (mock, quando USE_MOCK_DATA)
~35 entidades mock espelhando os DTOs: `symbol,candles,bb,regime,indicators,sr,volumeProfile,patterns,signal,confluence,confidenceBreakdown,capital,drawdown,equity,circuitBreaker,kelly,riskConfig,guardrails,behavioral,agents(6),strategies,orders(22),pendingOrders,hitl,journal(16),journalMetrics,journalScatter,heatmap,backtest,monteCarlo,walkForward,backtestConfig,alerts(6),alertThresholds`. (Campos detalhados por `data.js:64-403`.)

### 6.3 Estado por tela (screen_*.jsx) — dado → CT_API
- **overview**: metrics(period),equity,orders — `getMetrics/getEquity/getOrders`.
- **market**: pair,tf,candles,bb,indicators,regime,levels,volumeProfile,patterns,signal,confluence,ticker — Promise.all; `submitOrder`→OrderCreate{pair,side,quantity,price,strategy,agent_id:'manual-ui',confidence,reason,position_size_pct,stop_loss,take_profit?}.
- **orders**: orders,statusF,sideF; mapeia mock stop→stop_loss etc.
- **risk**: protections,cb,kelly,equity.
- **hitl**: config,orders(pending); decide→{action,operator_note,operator_id}; setLevel→{level,reason,operator}.
- **agents**: agents,configAgent; getAgentConfig→params, patchAgentConfig(draft).
- **observability**: events agrupados por case_id; lê activity,timestamp,attributes{failures,duration_ms,ran}.
- **journal**: entries,metrics; form{setup,emotion_before,stop_defined,plan_followed,pnl_pct,note}.
- **backtest**: config,result,mc,wf,jobId; polling getBacktestJob 1500ms.
- **settings**: sysConfig,riskConfig,alertConfig,agents; patchConfig/patchRiskConfig/patchAlertsConfig.
- **app.jsx**: routing por hash; polling pendingCount 15s; SSE subscribeAlerts→toast (severity critical/high). AlertDrawer: getAlertHistory(50)+SSE, slice 100.

### 6.4 `openapi.d.ts` — contrato transversal (TS gerado)
34 paths + `components.schemas` com ~50 DTOs espelhando 1:1 os Pydantic (envelopes `APIResponse_*_{_links?,data,meta?}`; DTOs OrderCreate/OrderOut/PortfolioMetricsOut/IndicatorsOut/RiskConfigOut/... + enums OrderSide, OrderStatus). Gerado por `npm run gen:types`; CI barra drift (`git diff --exit-code`).

---

## 7. Ciclo de vida ponta-a-ponta de um dado

Rastreamento de um sinal de trading, do mercado à métrica (todas as transformações do dado):

1. **Exchange OHLCV** `[ts,o,h,l,c,v]` → `StrategyAgent._analyze_market` → **analysis** (TechnicalIndicators + regime + S/R + volume).
2. analysis → `_build_market_data` → **market_data** (nested/flat) → `strategy.analyze` → resultado da estratégia (`entry,stop_loss,take_profit,position_size_pct,confidence`).
3. `_generate_signal` normaliza → **signal** `{action,entry_price,stop_loss,take_profit,position_size_pct,strategy,regime,market_context}`; orquestrador adiciona `symbol`.
4. **ledger** `log_signal{agent,signal}` (P). Gate de confiança <0.6 aborta.
5. signal → `RiskAgent.execute` → guardrails.validate_order(signal) → **validation** `{approved,issues,warnings,confidence}`; `log_validation` (P). Rejeição → **Alert** `risk_rejection` (P + SSE).
6. signal → `make_approval_handler` mapeia para **Order** (nota: `entry_price`→`price`, deriva `quantity` de `position_size_pct`). `OrderStore.submit` → INSERT `orders` (P) + XES `order_submitted`.
7. Se `notional≤threshold` → auto-fill (`order_fill` P); senão `wait_for_decision` (polling SQLite 2s). API `PATCH` grava `approved` (P). `log_hitl_approval` (P).
8. signal + quantity → `ExecutionAgent.execute` → exchange.create_order (paper) → **execution_result** `{order_id,executed_price,fee}`; `log_execution` + `log_fill{order_id,symbol,side,price,quantity,notional,fee}` (P); `_open_positions[order_id]` (P via PositionStore); `mark_filled` → `filled` (P).
9. Ciclo futuro: `_check_open_positions` detecta SL/TP → `log_position_closed{...,pnl,pnl_pct}` (P); `circuit_breaker.record_trade_result(pnl_pct)` (P em circuit_breaker_state).
10. `PortfolioMetricsCalculator.compute` relê `position_closed`+`order_fill` → **PortfolioMetrics** → `GET /v1/metrics` → **APIResponse[PortfolioMetricsOut]** → CT_API desembrulha `data` → tela overview.

Em paralelo: cada ciclo emite XES `agent_cycle_started/completed/failed` → `GET /v1/process/events` → tela observability (process mining).

---

## 8. Dados "perdidos na classe" / declarados-mas-não-usados

Dados atribuídos e **nunca lidos depois** (marca **X**), conforme pedido.
> **Estado (atualizado após Ondas 1–2, PR #68 + seguinte):** vários itens foram
> resolvidos — marcados ✅ abaixo. Ver `docs/plano-melhorias.md` e `CHANGELOG.md`.

| Dado | Local | Observação |
|---|---|---|
| ~~`RiskAgent.max_daily_loss_pct`~~ | `risk_agent.py` | ✅ **REMOVIDO (Onda 1)** — a perda-diária vive no `CircuitBreaker`, que tem o P&L; atributo era morto/enganoso |
| ~~`UnifiedOrchestrator.sandbox`~~ | `unified_orchestrator.py` | ✅ **REMOVIDO (Onda 1)** |
| ~~`UnifiedOrchestrator.chain_manager`~~ | `unified_orchestrator.py` | ✅ **REMOVIDO (Onda 1)** |
| ~~`AgentMemorySystem.short_term`~~ | `agent_memory.py` | ✅ **REMOVIDO (Onda 1)** |
| `SecureToolSandbox.memory_limit_mb` | `secure_executor.py:26` | declarado, não aplicado na execução (aberto) |
| `SecureToolSandbox.cpu_quota` | `secure_executor.py:27` | declarado, não aplicado (aberto) |
| `ContinuousEvaluator.baseline` (continuous_eval) | `continuous_eval.py:11` | atribuído None, nunca usado (aberto) |
| metrics `user_satisfaction`,`error_rate`,`response_time_p95` | `continuous_evaluator.py` (`AgentPerformanceEvaluator`) | chaves declaradas, nunca alimentadas (aberto) |
| `signal["market_context"]` | `strategy_agent.py:232` | construído mas o pipeline nunca lê (RiskAgent passa o signal inteiro) (aberto) |
| `analysis["fibonacci_levels"]` | `strategy_agent.py:126` | computado, só carregado/sanitizado, nunca consumido a jusante (aberto) |
| `strategy_result.{analysis,llm_used,llm_thesis,reasoning}` | `strategy_agent.py:89` | retornados; orquestrador só lê signal/confidence/stub_used (aberto) |
| `OrchestratorLoop.order_store` | `orchestrator_loop.py:220` | exposto "para inspeção/futuro" (aberto) |

Dados **carregados mas subutilizados**: `KellyCriterion`/`PositionSizer`/`CapitalProtections`.
🟡 **Parcial (Onda 2, ADR-006):** a fórmula central do Kelly virou fonte única
(`src/risk/position_sizing.full_kelly_fraction`) e o endpoint `GET /v1/risk/kelly`
agora a consome — `src/risk/` não é mais código morto. **Resta:** o pipeline ainda
dimensiona por `position_size_pct` simples (plugar Kelly/proteções no sizing é a
cauda do R5).

---

## 9. Anomalias e inconsistências de dados

Achados relevantes para refatoramento. **Estado atualizado após Ondas 1–2** (✅ = resolvido):

1. ✅ **Dois formatos de `market_data`** (§3.4) — **RESOLVIDO (Onda 2)**: `engine._build_market_data` agora computa um `TechnicalIndicators` real + `regime` (guarda de warmup), exercitando o mesmo caminho que o live; Grid/MeanReversion não ficam mais inertes no backtest.
2. **Ponte de nome `entry`→`entry_price`** (aberto): estratégias emitem `entry` (`mean_reversion.py:68`), mas guardrails/Order esperam `entry_price` — o `StrategyAgent._generate_signal` faz a normalização; um consumo direto do output da estratégia quebraria a validação.
3. ✅ **Mismatch de chave no registry de estratégias** — **RESOLVIDO (Onda 1)**: `mean_reversion` agora é emitida no regime `sideways` por `_REGIME_STRATEGY_MAP`; teste de consistência registry↔roteamento adicionado.
4. ✅ **`ab_tests.jsonl` não é JSON válido** — **RESOLVIDO (Onda 1)**: gravado via `json.dumps` (`ab_testing.py`).
5. 🟡 **Colisões de nome de tipo** — **PARCIAL (Onda 2, R2)**: renomeados por propósito — `SquadOrchestrator`(protocols)→`A2ASquad`, `AdaptivePlanner`(replanner)→`AdaptiveReplanner`, `ContinuousEvaluator`(evaluator)→`AgentPerformanceEvaluator`, `MemoryStore`(forgetting)→`RelevanceMemoryStore`. **Resta** `Guardrail`×2 (ligado a R2b/R3 — duas fundações de agente/política).
6. **Duas políticas de validação de ordem** com campos diferentes: `GuardrailSystem` lê `market_context/action/entry_price`; `SecurityConfig.validate_order` lê `notes/exchange/position_size_pct`.
7. **`CandleOut` usa `lo`** (não `l`) para low (`schemas.py:216`) — divergência de convenção vs OHLCV interno `[o,h,l,c]`.
8. **Namespace `/v1/agents/{id}/config`** servido por dois routers (`agents` GET, `config` PATCH).

---

> **Documento gerado por análise estática dos scripts do repositório.** Referências `arquivo:linha` preservam rastreabilidade. Nenhum código foi alterado. Complementa `docs/uml/arquitetura-uml.md` e `docs/architecture/arquitetura.md`.
