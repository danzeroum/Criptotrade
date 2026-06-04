# Validação dos Planos de Implementação — Criptotrade

> **Objetivo deste documento:** validar os cinco planos entregues (Refatoração Frontend/Backend, BPM,
> Design UX, Arquitetura de Software e Design de API) contra o **estado real do repositório**,
> corrigir afirmações incorretas e **acrescentar o que falta** para que um desenvolvedor consiga
> implementar sem retrabalho.
>
> Método: varredura do código em `src/`, `config/`, `docker/`, `tests/` na branch de trabalho.
> Cada afirmação abaixo é rastreável a um arquivo/linha real.

---

## 0. Veredito geral

Os planos são **bem estruturados e majoritariamente acionáveis**, mas foram escritos **sem leitura
profunda do código**. Eles assumem um repositório mais "vazio" do que o real e contêm **erros factuais
que mudam o esforço e o desenho da solução**. Antes de implementar, três correções são obrigatórias:

1. **O ciclo de trading JÁ EXISTE e está testado** — não precisa ser "descoberto" nem inferido.
2. **O modelo HITL real é diferente do descrito** (4 níveis por trust-score, não 6 por valor em US$).
3. **A engine de métricas (Sharpe/WinRate/Drawdown) NÃO existe** — precisa ser construída do zero;
   o `ledger.py` apenas grava eventos.

Sem essas correções, o desenvolvedor implementaria contra premissas erradas (ex.: criar slider HITL
0–5 que não casa com o backend; "expor" métricas que ninguém calcula; modelar em BPMN um processo
"inexistente" que na verdade está pronto).

**Completude por plano:**

| Plano | Acionável? | Erros factuais | Lacunas críticas |
|-------|-----------|----------------|------------------|
| Refatoração FE/BE | ⚠️ Parcial | Médio (ledger calcula métricas; orchestrator) | Engine de métricas; bridge HITL |
| BPM | ⚠️ Parcial | Alto (P1 "não existe"; DMN não bate) | Aponta arquivos errados; ignora YAML existente |
| Design UX | ✅ Bom | Baixo (HITL 0–5; timeout) | Sem backend de alerts/timeout para sustentar wireframes |
| Arquitetura | ⚠️ Parcial | Médio (LLM; compose; Postgres) | Ignora 2 composes e Gemini; Redis Streams é exagero p/ 1 processo |
| Design de API | ⚠️ Parcial | Médio (HITL 0–5; Pydantic v1) | Código não roda como está; testes falham; deps faltando |

---

## 1. Tabela de validação factual (afirmação do plano × realidade do código)

| # | Afirmação nos planos | Realidade no repositório | Veredito |
|---|----------------------|--------------------------|----------|
| 1 | Não existe `src/api/` | Correto — não há | ✅ |
| 2 | `dashboard/app.py` é placeholder com `"--"` | Correto (`src/dashboard/app.py`, 473 bytes) | ✅ |
| 3 | "`ledger.py` provavelmente calcula P&L" | **FALSO.** `TradingLedger` é **append-only JSONL** (`log_signal/validation/execution/hitl_approval`, `get_recent_trades`). **Não calcula** Sharpe, Win Rate, Drawdown nem P&L. | ❌ |
| 4 | HITL tem "níveis 0–5" / API com thresholds $1.000/$5.000 | **FALSO.** `ProgressiveAutonomyManager` tem **4 níveis (0–3)** derivados de **trust-score** (cortes 0.4/0.6/0.8), não de valor em dólar, e **não são setáveis pelo usuário**. | ❌ |
| 5 | HITL precisa de UI para aprovar/rejeitar | Parcialmente coberto, mas **omite que é fail-closed**: `approval_handler=None` ⇒ nega tudo. Vale para `SquadOrchestrator` e `ProgressiveAutonomyManager`. | ⚠️ |
| 6 | "`orchestrator.py` monolítico chama agents diretamente" | **FALSO.** `src/orchestrator.py` integra `SafeAgentBase`+RAG+MCP+`ContinuousEvaluator`; **não faz trading**. `unified_orchestrator.py` é um squad de **desenvolvimento de software** (architect/developer/auditor/designer/ops), **não de trading**. | ❌ |
| 7 | "Processo P1 (ciclo de trading) não está modelado em lugar nenhum" | **FALSO no código.** Está **implementado e testado** em `src/orchestration/squad_orchestrator.py` → `SquadOrchestrator.analyze_and_trade()`: strategy → gate de confiança (<0.6 pula) → risk → HITL (fail-closed) → execution → ledger. Coberto por `tests/integration/test_trading_flow.py`. **Verdadeiro só quanto a BPMN** (não há diagrama). | ❌ |
| 8 | `recovery_agent`/`exploration_agent` são "stubs de trading" | **MISCARACTERIZADO.** São agentes **de segurança**: `ExplorationAgent(scanner_tool)` varre vulnerabilidades; `RecoveryAgent(remediation_tool)` faz remediação. Não são "recuperação de trading". São wrappers finos, mas com propósito distinto do alegado. | ❌ |
| 9 | DMN de risco: drawdown/volatilidade/exposição; regras hardcoded em `guardrails.py` | Guardrails reais são **por ordem**: `check_position_size` (5%), `check_stop_loss` (obrigatório), `check_risk_reward` (2.5), `check_market_conditions` (**TODO vazio**). Guardrails de **portfólio** (drawdown/volatilidade/exposição) **não existem**. A tabela DMN proposta é **aspiracional**, não reflete o código. | ⚠️ |
| 10 | "Externalizar regras para YAML/DMN" | **Já existe** `config/strategies/risk_params.yaml` (extensíssimo: limites, circuit breaker, diversificação, etc.). O problema real: `guardrails.py` e `risk_agent.py` **ignoram o YAML e hardcodam** `5.0`/`3.0`/`2.5`. Nenhum plano encontrou esse arquivo. | ❌ |
| 11 | Propor `docker-compose.yml` novo (postgres+redis+grafana) | **Já existem DOIS composes**: raiz (`app`+`prometheus`) e `docker/docker-compose.yml` (**postgres+redis+grafana+prometheus**, com secrets sem default já endurecidos). Tarefa real = **reconciliar/estender**, não criar do zero. | ❌ |
| 12 | LLM = OpenAI / Anthropic | **FALSO.** Primário é **Google Gemini** (`langchain-google-genai`, `GOOGLE_API_KEY`); OpenAI é **backup**. Diagrama de contexto C4 precisa ser corrigido. | ❌ |
| 13 | Migrar `ledger.py` → PostgreSQL | Default atual é **SQLite** (`DATABASE_URL=sqlite:///./data/trading.db`) e o ledger é **arquivo JSONL**, nem usa SQLAlchemy. Migração é maior do que "trocar a connection string". | ⚠️ |
| 14 | "`tests/` existe mas sem análise de cobertura" | Já há suíte real: `test_guardrails`, `test_agents`, `test_trading_flow`, `test_consensus_mechanism`, `test_unified_orchestration`, `test_agent_integration`, `test_security_sandbox`, `test_emergent_behavior`; `pytest-cov` no requirements. | ⚠️ |
| 15 | Circuit breaker no `exchange_client.py` | Correto — **não há** retry/backoff/circuit breaker (`grep` por circuit/retry/backoff = 0). Mas o cliente já é async (`asyncio.to_thread`) e sandbox/paper-aware. | ✅ |
| 16 | `mcp_integration.py` é "stub fictício (167 bytes)" | É um **shim de compatibilidade** que reexporta `MCPToolRegistry`. Não é integração fictícia; é fino de propósito. | ⚠️ |
| 17 | `continuous_eval.py` vs `continuous_evaluator.py` (duplicação) | Correto — ambos existem. **Some-se**: existem **dois** `squad_orchestrator.py` (`src/orchestration/` e `src/protocols/`). Risco de confusão de import. | ✅ |
| 18 | Dependências FastAPI/uvicorn/SQLAlchemy ausentes | **Já presentes** em `requirements.txt` (fastapi 0.109, uvicorn, sqlalchemy 2.0, ccxt, prometheus-client). **Faltam** as deps que os planos usam (ver §6). | ⚠️ |

---

## 2. Lacunas críticas não cobertas por NENHUM plano

1. **Engine de métricas inexistente.** Sharpe/Win Rate/Drawdown/P&L precisam ser **calculados** a
   partir dos eventos do ledger. Hoje o ledger só tem `signal/validation/execution/hitl_approval` —
   **não há preço de fill, quantidade realizada, nem fechamento de posição** registrados de forma
   estruturada. Sem enriquecer o ledger, é impossível calcular P&L. **Esta é a dependência-raiz de
   todo o dashboard** e está subestimada em todos os planos.

2. **Bridge assíncrono de aprovação HITL.** Como o backend é fail-closed e a aprovação é um
   `Callable` async (`approval_handler(order) -> bool`), a UI de "Aprovar/Rejeitar" exige um
   mecanismo de **request/response pendente** entre API e orquestrador (fila de ordens pendentes +
   resolução por `order_id`). Os wireframes assumem isso pronto; não está.

3. **Timeout/expiração de ordens pendentes.** O wireframe HITL mostra "Expira em 4:32", mas o backend
   **não tem timeout** — ordens pendentes não expiram nem têm fallback. Precisa ser implementado
   (ou o elemento de UI removido).

4. **Barramento de alertas inexistente.** `guardrails.py` só faz `logger.warning`. Não há pub/sub,
   fila nem persistência de alertas. O feed de guardrails (UI) e o `/v1/alerts` (SSE) **não têm fonte
   de dados**. Precisa de um `AlertSink`/event bus antes do SSE.

5. **Reconciliação dos orquestradores.** Há três "orquestradores" com responsabilidades distintas
   (`orchestrator.py` = RAG/MCP; `unified_orchestrator.py` = squad de dev; `squad_orchestrator.py` =
   trading). A API deve depender **exclusivamente** do `SquadOrchestrator` para trading; isso precisa
   estar explícito para o dev não cablear no orquestrador errado.

6. **`config.py` e carregamento de `risk_params.yaml`.** Existe `src/core/config.py` (7.6KB) e o YAML,
   mas guardrails/risk_agent não os consomem. A "externalização DMN" é, na prática, **fazer o código
   ler o YAML que já existe** — tarefa muito menor (e mais segura) do que adotar um motor DMN.

7. **Segurança/auth na API.** Hoje as portas 8000/8501 não têm auth. O plano de API propõe API-Key —
   ok — mas falta: rotação de chaves, escopo por rota e o fato de que `EXCHANGE_API_KEY` real só deve
   existir no container `orchestrator`, **nunca** acessível pela borda HTTP.

---

## 3. Correções e complementos — por plano

### 3.1 Refatoração Frontend/Backend

**Manter:** diagnóstico do frontend cego; caminho crítico ledger→API→app; faseamento.

**Corrigir:**
- O passo "Conectar `ledger.py` → `/metrics` retornando Sharpe/WinRate/Drawdown reais" **não é uma
  conexão, é uma construção**. Adicionar um módulo `src/core/metrics.py` (ou
  `src/evaluation/portfolio_metrics.py`) que:
  1. Enriqueça o ledger com eventos de **fill** (preço, qty, fee, timestamp) e **fechamento de
     posição** (P&L realizado);
  2. Calcule Sharpe (retornos diários), Win Rate (trades fechados com P&L>0), Max Drawdown (curva de
     equity), exposição e nº de posições abertas;
  3. Exponha via serviço consumido pelo `/v1/metrics`.
- `st.auto_refresh` não existe na API do Streamlit citada. Usar `st.experimental_rerun` + `time`/
  `st_autorefresh` (pacote `streamlit-autorefresh`) ou o `st.fragment(run_every=...)` (Streamlit ≥1.33;
  o pin atual é **1.31.0**, então **subir a versão** ou usar `streamlit-autorefresh`).

**Acrescentar:**
- Definir **contrato de dados de fill** no ledger antes de qualquer endpoint (é o gargalo real).
- O dashboard deve degradar com elegância: estados `Carregando…`/`Sem dados`/`API offline`, nunca `--`
  ambíguo (alinha com o achado P0 do plano de UX).

### 3.2 BPM

**Manter:** valor de BPMN/DMN/Process Mining para este domínio; ideia de event log XES.

**Corrigir:**
- **P1 já está implementado** (`SquadOrchestrator.analyze_and_trade`) e **testado**. A entrega correta
  não é "modelar um processo inexistente", e sim **documentar em BPMN o fluxo já existente** e cobrir
  os gaps reais: (a) `check_market_conditions` é TODO; (b) não há timer DCA real disparando o ciclo;
  (c) não há tratamento de erro de conexão da exchange (sem circuit breaker).
- A **DMN proposta não corresponde aos guardrails reais.** A decisão real hoje é per-order
  (position size, stop loss, risk-reward). Para a DMN de portfólio (drawdown/volatilidade/exposição)
  ser real, é preciso **antes** implementar guardrails de portfólio (que não existem).
- "Externalizar regras de `guardrails.py`" → na prática: **fazer `guardrails.py` e `risk_agent.py`
  lerem `config/strategies/risk_params.yaml`** (já existe e é rico). Eliminar os literais `5.0`/`3.0`/
  `2.5`. Isso resolve o acoplamento sem introduzir um motor DMN.

**Acrescentar:**
- O event log XES deve sair do **enriquecimento do ledger** (mesmo dado da engine de métricas). Reusar,
  não criar `event_log.py` paralelo. Mapear `case_id = order_id`, `activity ∈ {signal_generated,
  risk_validation, hitl_decision, order_executed}`, `actor = agent/operator`.

### 3.3 Design UX

**Manter:** personas, mapa de necessidades, heurísticas de Nielsen, paleta acessível (WCAG AA),
priorização P0→P3. É o plano mais sólido.

**Corrigir:**
- **Slider de autonomia 0–5 → 0–3** (ou decidir conscientemente expandir o backend; ver §3.5). As
  descrições por nível devem refletir os nomes reais: `full_human_control`, `human_approval_critical`,
  `human_notification`, `full_autonomy`. **Não há semântica de US$** no modelo atual.
- O card HITL mostra "Confiança 87%", "Exposição 42%→48%": **confiança existe** (`strategy_result
  ["confidence"]`), mas **exposição de portfólio não é calculada** hoje. Marcar como "depende da engine
  de métricas/portfólio".
- "Expira em 4:32": **não há timeout no backend**. Ou implementar (§2.3) ou remover da UI v1.
- "Razão do agente em linguagem natural": hoje o sinal é um dict; o `reason` precisa ser **produzido**
  pelo strategy/risk agent e propagado pela API (campo `reason` no schema de ordem — bom que o plano
  de API já prevê).

**Acrescentar:**
- Estado **"sistema pausado/circuit breaker ativo"** na barra global — o `risk_params.yaml` já define
  circuit breaker (4% diário / 3 perdas seguidas / cooldown 24h); a UI deve refletir esse estado.

### 3.4 Arquitetura de Software

**Manter:** atributos de qualidade (-ilities), trade-offs explícitos, C4, health contract, feature
flags por agent, circuit breaker no exchange client.

**Corrigir:**
- **Diagrama de contexto:** trocar "OpenAI/Anthropic" por **Google Gemini (primário) + OpenAI
  (backup)**.
- **Não criar `docker-compose.yml` do zero.** Reconciliar os dois existentes. O de `docker/` já tem
  postgres+redis+grafana+prometheus com secrets endurecidos. Decisão a tomar: **um app monolítico
  (atual, expõe 8000+8501)** vs **split em `dashboard`/`api`/`orchestrator`**. Para a fase de demo, o
  split é desejável mas **não é pré-requisito** — pode-se rodar API+dashboard no mesmo container e
  evoluir. Registrar como trade-off.
- **Redis Streams / fila assíncrona entre orchestrator e agents:** para um sistema **single-operator,
  1 processo**, o acoplamento atual (chamadas async diretas no `SquadOrchestrator`) é **adequado e mais
  simples**. A alegação de acoplamento "O(n²)" é exagerada — são chamadas lineares orquestradas. Adotar
  Redis Streams é uma decisão de escala futura, não de demo. Manter como trade-off explícito (coerente
  com a própria "Lei da Arquitetura" do plano), **não** como tarefa de Sprint inicial.

**Acrescentar:**
- ADR formal (já há `docs/ADR/`) para: (1) SQLite→Postgres e migração do ledger JSONL; (2) split de
  containers; (3) síncrono vs Redis Streams. Use o diretório de ADR existente.
- Persistência: o ledger é **arquivo JSONL** num volume. Em container efêmero isso é perda de dados —
  garantir volume nomeado ou migrar para Postgres **antes** de tratar métricas como confiáveis.

### 3.5 Design de API

**Manter:** versionamento `/v1`, substantivos no plural, envelope `APIResponse`, 202 p/ ordem pendente,
501 p/ recurso não implementado, SSE p/ alerts, API-Key como auth inicial, migration SQL, suíte de
testes. O desenho é bom.

**Corrigir (bloqueadores — o código como está NÃO roda / testes falham):**
- **Pydantic v2** (repo usa `pydantic==2.6.0`):
  - `@validator` → `@field_validator` (e assinatura nova). O exemplo em `orders.py` usa `@validator`.
  - `.dict()` → `.model_dump()`.
  - `Query(..., regex=...)` → `Query(..., pattern=...)`.
  - `APIResponse._links`: campo com **underscore inicial** é tratado como atributo privado no Pydantic
    v2 e **não serializa** como JSON `_links`. Usar `links: Links = Field(alias="_links")` +
    `model_config = ConfigDict(populate_by_name=True)`.
  - `Generic[T]` + `BaseModel`: ok no v2, mas requer `from pydantic import BaseModel` + tipagem
    `APIResponse[Order]` com modelos **definidos antes** do uso.
- **Ordem de definição:** em `metrics.py`, `PortfolioMetrics` é usado no `response_model` **antes** de
  ser definido. Mover schemas para `src/api/schemas/` e importar.
- **Schemas referenciados mas não definidos:** `Order`, `Alert`, `AgentDetail`, `HITLConfig`,
  `HITLConfig`, `Links`/`Meta` em cada rota. Centralizar em `schemas/`.
- **Handler 422 ausente:** os testes esperam `body["error"]=="validation_error"` e `body["field"]`
  contendo `"pair"`. O FastAPI **não** retorna esse formato por padrão — é preciso registrar um
  `@app.exception_handler(RequestValidationError)` que converta para o envelope. **Sem isso,
  `test_create_order_invalid_pair_returns_422` falha.**
- **HITL 0–5 vs 0–3:** decisão de produto necessária (ver pergunta ao final). O schema `AutonomyLevel`
  (0–5, thresholds US$) **contradiz** o backend. Reconciliar: ou (a) API expõe 0–3 espelhando
  `ProgressiveAutonomyManager`, ou (b) expandir o manager para suportar override manual + faixas.

**Acrescentar:**
- **Dependências faltantes** no `requirements.txt` para a API proposta rodar (ver §6).
- **Fonte real do SSE:** `/v1/alerts` consome `redis.pubsub("criptotrade:alerts")`, mas **ninguém
  publica** nesse canal hoje. Implementar o `AlertSink` em `guardrails.py`/circuit breaker antes.
- **Bridge HITL:** `POST /v1/orders` (202) + `PATCH /v1/orders/{id}/status` precisam de um store de
  ordens pendentes e de um `approval_handler` que **resolva** a Future quando o operador decide.
  Especificar esse mecanismo (ex.: tabela `orders` em estado `pending` + polling/await por `order_id`).
- **Isolamento de credenciais:** garantir que `EXCHANGE_API_KEY/SECRET` só existam no processo
  `orchestrator`; a borda HTTP nunca deve expô-las nem aceitá-las como entrada.

---

## 4. Plano consolidado e ordenado (corrigido) para o desenvolvedor

Ordem por **dependência técnica**, não só por impacto de demo.

### Fase 0 — Fundação de dados (pré-requisito de tudo) — 3–5 dias
1. **Enriquecer o ledger**: registrar `fill` (preço, qty, fee, ts) e `position_closed` (P&L
   realizado). Definir schema do evento. *(desbloqueia métricas e XES)*
2. **`src/core/metrics.py`**: calcular Sharpe, Win Rate, Max Drawdown, P&L, exposição, posições
   abertas a partir do ledger. Testes unitários com ledger sintético.
3. **Decisão de persistência (ADR)**: manter JSONL em volume nomeado para a demo **ou** migrar para
   SQLite/Postgres via SQLAlchemy. Garantir que dados sobrevivam ao restart do container.

### Fase 1 — API mínima + dashboard conectado — 1 semana
4. **`src/api/`** (FastAPI, Pydantic **v2**): `/health`, `/v1/metrics`, `/v1/positions`,
   `/v1/orders` (GET). Envelope `APIResponse`, handler `RequestValidationError`, API-Key middleware.
5. **Refatorar `app.py`** para consumir a API (`httpx`) com estados de loading/erro e auto-refresh
   (`streamlit-autorefresh` ou subir Streamlit p/ usar `st.fragment(run_every=...)`).
6. **Testes de API** (ajustados ao Pydantic v2) verdes, incluindo o caso 422.

### Fase 2 — HITL operacional — 1–2 semanas
7. **Bridge de aprovação**: store de ordens `pending` + `approval_handler` que resolve por `order_id`;
   `POST /v1/orders` (202) e `PATCH /v1/orders/{id}/status` (409 se não-pending, 422 sem `operator_note`
   ao rejeitar).
8. **(Opcional) timeout/expiração** de ordens pendentes + fallback fail-closed.
9. **UI HITL** (níveis **0–3**, fila de pendentes, aprovar/rejeitar, histórico). Refletir circuit
   breaker / sistema pausado.

### Fase 3 — Observabilidade e regras — 1–2 semanas
10. **`config/risk_params.yaml` como fonte única**: `guardrails.py` e `risk_agent.py` leem o YAML;
    remover literais hardcoded. *(esta é a "externalização DMN" real)*
11. **AlertSink + `/v1/alerts` (SSE)**: guardrails e circuit breaker publicam alertas; persistir
    histórico; UI consome o feed.
12. **`/v1/agents`**: status real dos agentes (501 honesto p/ não-implementados; distinguir agentes de
    segurança dos de trading).
13. **BPMN do P1 existente** em `docs/bpmn/` + event log XES derivado do ledger (PM4Py opcional).

### Fase 4 — Resiliência e escala (trade-offs futuros) — conforme necessidade
14. **Circuit breaker no `exchange_client.py`** (CLOSED→OPEN→HALF-OPEN) + retry/backoff.
15. **Feature flags por agent** via env.
16. **(Só se escalar)** Redis Streams entre orchestrator e agents; split de containers
    dashboard/api/orchestrator. Decidir por ADR.

---

## 5. Definition of Done / critérios de aceite

- [ ] Dashboard nunca mostra `--`: exibe valor real, `Carregando…`, `Sem dados` ou `API offline`.
- [ ] `GET /v1/metrics` retorna Sharpe/WinRate/Drawdown **calculados** do ledger, com testes.
- [ ] Ordem com par inválido retorna **422** no envelope `{error, message, field}` (teste verde).
- [ ] Aprovar/rejeitar no dashboard altera o estado real da ordem; rejeição exige `operator_note`.
- [ ] Backend permanece **fail-closed**: sem handler configurado, nenhuma ordem executa.
- [ ] Nível de autonomia exibido na UI **bate** com `ProgressiveAutonomyManager` (0–3 ou modelo
      reconciliado).
- [ ] `guardrails.py`/`risk_agent.py` leem limites de `risk_params.yaml` (zero literais duplicados).
- [ ] Dados do ledger sobrevivem a restart do container (volume nomeado ou DB).
- [ ] `pytest` (incl. `tests/integration/test_trading_flow.py`) continua verde.

---

## 6. Dependências a adicionar (para os planos rodarem)

Presentes: `fastapi`, `uvicorn`, `streamlit`, `sqlalchemy`, `ccxt`, `prometheus-client`, `pytest*`.

Faltam, conforme o que os planos usam:

| Pacote | Para quê | Plano que exige |
|--------|----------|-----------------|
| `httpx` | dashboard → API (cliente) | Refatoração / Design |
| `streamlit-autorefresh` (ou Streamlit ≥1.33) | auto-refresh do dashboard | Refatoração / UX |
| `sse-starlette` | `/v1/alerts` via SSE | API |
| `redis` (cliente) | pub/sub de alertas, se adotado | API / Arquitetura |
| `asyncpg`/`psycopg[binary]` + `alembic` | Postgres + migrations (se migrar) | Arquitetura / API |
| `pm4py` | process mining sobre o event log | BPM (opcional) |
| `slowapi` (ou impl. própria) | rate limit do `RateLimitMiddleware` | API |

> Atenção ao comentário já existente no `requirements.txt`: **não** adicionar o backport `asyncio`.

---

## 7. Decisão de produto necessária antes de codar o HITL

O ponto que mais afeta UX, API e backend simultaneamente é o **modelo de autonomia**. As opções:

- **(A) Espelhar o backend atual (0–3, trust-score).** Menor esforço, coerente com o código e os
  testes; a UI vira read-only do nível derivado + override de aprovação por ordem.
- **(B) Expandir para 0–5 com faixas/override manual** como nos planos de UX/API. Mais alinhado aos
  wireframes, mas exige refatorar `ProgressiveAutonomyManager`, novos testes e migração de
  `AUTONOMY_LEVEL` no `.env`.

Recomendação: **(A) para a demo**, evoluindo para (B) só se o produto exigir controle manual de
faixas. Registrar em ADR.
