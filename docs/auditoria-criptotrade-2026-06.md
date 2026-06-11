# Auditoria de Código & Plano de Remediação — CriptoTrade
**Versão:** 1.0 · **Data:** 2026-06-11 · **Idioma:** pt-BR  
**Coordenador:** Agente AI (Claude) · **Repositório:** `danzeroum/criptotrade`  
**Branch de dev (código):** `claude/youthful-gauss-r1fdwb`

---

## 1. Visão Geral, Metodologia e Limitação de Produção

### 1.1 Objetivo

Este documento consolida a auditoria do sistema CriptoTrade, cruza os laudos de dois analistas externos com a leitura direta do código-fonte e estabelece o backlog de remediação priorizado (P0–P3) para uso do desenvolvedor responsável pelas correções.

### 1.2 Metodologia

| Insumo | Fonte | Confiança |
|--------|-------|-----------|
| Leitura de código | Arquivos-fonte do repo (HEAD da branch) | Alta — verificável |
| Laudo 1º analista | Crítica ao plano de remediação | Média — interpretação de código |
| Laudo 2º analista | Sondagem de endpoints em produção | Baixa-Média — condicionada ao ambiente |
| ADRs | `docs/adr/001`, `002`, `003` | Alta — decisões formais registradas |

As referências de código seguem o formato `arquivo:linha` e foram verificadas contra o HEAD do repositório em 2026-06-11.

### 1.3 Limitação Central: Produção Inacessível do Sandbox

> **Este sandbox não consegue alcançar `https://criptotrade.buildtovalue.cloud/`.**  
> A política de egress do ambiente de auditoria (allowlist que libera apenas GitHub/PyPI) bloqueia com `403 host_not_allowed` qualquer requisição ao domínio do produto, bem como `example.com` e `ipify`.

Consequências diretas:

- Achados de runtime do 2º analista **não foram validados em primeira mão** — foram cruzados contra o código-fonte.
- Todos os itens marcados como "a confirmar em P0-0" permanecem hipóteses até o dev rodar `P0-0` no host com acesso real à produção.
- Nenhuma afirmação sobre estado de produção é feita como fato neste documento.

---

## 2. Validação Cruzada dos Analistas

### 2.1 Achados do 2º Analista (Sondagem de Produção) × Código

| Achado do 2º analista | Veredicto | Evidência no código |
|-----------------------|-----------|---------------------|
| Kelly degenera para `full_kelly=0` e `risk_of_ruin=100%` com ledger vazio | ✅ **Confirmado** | `risk.py:176-197` — `win_rate` default `0.5`, `avg_win/avg_loss` default `1.0`, matemática produz exatamente esses valores |
| 500 em texto plano para exceções não tratadas | ✅ **Confirmado** | `main.py:103-139` — handlers apenas para `RequestValidationError` e `HTTPException`; sem catch-all `Exception`; Starlette retorna `"Internal Server Error"` plano |
| `/openapi.json` 404 em produção | ✅ **Confirmado como risco** | `main.py:70-77` — `openapi_url` não setado → default FastAPI `/openapi.json` (sem prefixo `/v1`); se nginx só proxia `/v1/*`, a rota cai fora do proxy |
| `GET /v1/orders` sem paginação real | ✅ **Confirmado** | `orders.py:42-45` — `store.list()` sem `limit`/`offset`; `Meta` retorna `page=1, per_page=total` — pseudo-meta, não paginação real |
| Sem validação de par de mercado | ✅ **Confirmado** | `market.py:40-43` — `_decode_pair()` normaliza `BTC-USDT`→`BTC/USDT` mas sem whitelist; qualquer string decodificável é aceita |
| Dados sintéticos (exchange simulada) | ✅ **Confirmado como by-design** | `docker-compose.yml` define `EXCHANGE_DRY_RUN=true`; ADR-001 documenta formalmente a estratégia Paper Trading First |
| API aberta sem `API_KEYS` | ⚠️ **Não verificável aqui — deferido P0-0** | `main.py:46-48` confirma fail-open; estado real da variável em prod desconhecido |
| `dry_run` desligável sem auth | ⚠️ **Não verificável aqui — deferido P0-0** | `config.py` expõe `PATCH /v1/config`; `main.py:46` é fail-open se `API_KEYS` vazio |
| CORS `*` em produção | ⚠️ **Código confirma, prod não verificada** | `main.py:82` — `CORS_ORIGINS` default `"*"` |
| `open_positions` com contagem crescente | ⚠️ **Não verificável aqui — deferido P0-0** | Requer inspeção do SQLite de prod + ciclo do orquestrador |
| "`GET /v1/orders` congela a conexão com a exchange" | ⚠️ **Corrigido/discordância técnica** | `orders.py:42` — `store.list()` lê SQLite local, não acessa a exchange; causa real: resultado ilimitado + possível contenção de lock WAL |
| Console React = protótipo sem valor de produção | ❌ **Discordância** | `index.html` + `app.jsx` usam `API_BASE=""` (relativo, sem mock); PRs #25–30 integrados; `USE_MOCK_DATA` é flag de fallback, não default ativo |

### 2.2 Crítica do 1º Analista × Plano

| Item da crítica | Veredicto | Ação no backlog |
|----------------|-----------|-----------------|
| Reconciliação de contagem de endpoints (43 vs 37 vs 34) | ✅ Aceito | Seção 3 reconcilia formalmente |
| Auth como bloqueante pré-produção | ✅ Aceito | P0-1 |
| `_jobs` em memória (`backtest.py:33`) | ✅ Aceito | P2-1 |
| Cola de deploy ausente = risco de divergência código↔prod | ✅ Aceito | P3-2 |
| Vite vs import-map para build do console | ✅ Aceito (dois tradeoffs apresentados) | P3-1 |
| `/process/events` é feature de PM, não bug | ✅ Aceito | P2-3 (requalificado) |
| Streamlit como dev-tool, não frontend de produção | ✅ Aceito | P2-4 (documentar separação) |
| Verificação pós-push necessária | ✅ Aceito | Critério de aceite em cada item |
| Cobertura "inflada por skips" | ❌ Rejeitado | Sem marcadores `skip`/`xfail` no código; testes rodam com `DummyExchange`; 138 testes reais (README) |

---

## 3. Mapeamento do Backend

### 3.1 Reconciliação de Contagem de Rotas

| Nível | Contagem | Composição |
|-------|----------|------------|
| **Rotas no router** | ~43 | Inclui variantes de path (`/orders`, `/orders/{id}/status`), stubs `501`, `/health`, rotas de docs auto-geradas |
| **Endpoints de negócio `/v1/*`** | ~37 | Exclui `/health` e rotas internas do FastAPI |
| **Sondados pelo 2º analista** | ~34 | Diferença = stubs marcados `501 Not Implemented` + rotas não documentadas |

**Arquivos de rotas** (`src/api/routes/`):

| Arquivo | Prefixo | Endpoints principais |
|---------|---------|----------------------|
| `agents.py` | `/v1/agents` | `GET /`, `GET /{id}`, `GET /{id}/config`, `PATCH /{id}/config` |
| `alerts.py` | `/v1/alerts` | `GET /history`, `GET /config`, `PATCH /config`, `GET /` (SSE) |
| `backtest.py` | `/v1/backtest` | `POST /run`, `POST /montecarlo`, `POST /walkforward`, `GET /jobs/{id}` |
| `config.py` | `/v1/config` | `GET /`, `PATCH /` |
| `hitl.py` | `/v1/hitl` | `GET /config`, `PATCH /config` |
| `journal.py` | `/v1/journal` | `GET /`, `POST /`, `GET /metrics` |
| `market.py` | `/v1/market` | `GET /{pair}/candles`, `/{pair}/indicators`, `/{pair}/regime`, `/{pair}/levels`, `/{pair}/volume-profile`, `/{pair}/patterns`, `/{pair}/signal` |
| `metrics.py` | `/v1/metrics` | `GET /`, `GET /equity` |
| `orders.py` | `/v1/orders` | `GET /`, `POST /`, `PATCH /{id}/status` |
| `process.py` | `/v1/process` | `GET /events` |
| `risk.py` | `/v1/risk` | `GET /protections`, `GET /circuit-breaker`, `GET /kelly`, `GET /config`, `PATCH /config` |
| `main.py` | `/` | `GET /health` |

### 3.2 Matriz de Consumo — Frontend × Endpoint

| Endpoint | Console React (`apiClient.js`) | Dashboard Streamlit (`app.py`) |
|----------|-------------------------------|-------------------------------|
| `GET /health` | `getHealth()` | ✅ linha 74 |
| `GET /v1/metrics` | `getMetrics(p)` | ✅ linha 95 |
| `GET /v1/metrics/equity` | `getEquity(p)` | — |
| `GET /v1/hitl/config` | `getHITL()` | ✅ linha 75 |
| `PATCH /v1/hitl/config` | `patchHITL(body)` | ✅ linha 132 |
| `GET /v1/orders` | `getOrders(q)` | ✅ linhas 144, 282 |
| `PATCH /v1/orders/{id}/status` | `decideOrder(id, body)` | ✅ linhas 158, 169 |
| `GET /v1/agents` | `getAgents()` | ✅ linha 183 |
| `GET /v1/agents/{id}/config` | `getAgentConfig(id)` | ✅ linha 198 |
| `PATCH /v1/agents/{id}/config` | `patchAgentConfig(id, body)` | — |
| `GET /v1/alerts` (SSE) | `subscribeAlerts()` | — |
| `GET /v1/alerts/history` | `getAlertHistory(n)` | ✅ linha 313 |
| `PATCH /v1/alerts/config` | `patchAlertsConfig(body)` | — |
| `GET /v1/market/{pair}/candles` | `getCandles(pair, tf, limit)` | — |
| `GET /v1/market/{pair}/indicators` | `getIndicators(pair)` | — |
| `GET /v1/market/{pair}/regime` | `getRegime(pair)` | — |
| `GET /v1/market/{pair}/levels` | `getLevels(pair)` | — |
| `GET /v1/market/{pair}/volume-profile` | `getVolumeProfile(pair)` | — |
| `GET /v1/market/{pair}/patterns` | `getPatterns(pair)` | — |
| `GET /v1/market/{pair}/signal` | `getSignal(pair)` | — |
| `GET /v1/risk/protections` | `getProtections()` | — |
| `GET /v1/risk/circuit-breaker` | `getCircuitBreaker()` | — |
| `GET /v1/risk/kelly` | `getKelly()` | — |
| `GET /v1/risk/config` | `getRiskConfig()` | — |
| `PATCH /v1/risk/config` | `patchRiskConfig(body)` | — |
| `POST /v1/backtest/run` | `runBacktest(body)` | — |
| `POST /v1/backtest/montecarlo` | `runMonteCarlo(body)` | — |
| `POST /v1/backtest/walkforward` | `runWalkForward(body)` | — |
| `GET /v1/backtest/jobs/{id}` | `getBacktestJob(id)` | — |
| `GET /v1/journal` | `getJournal()` | — |
| `POST /v1/journal` | `addJournalEntry(body)` | — |
| `GET /v1/journal/metrics` | `getJournalMetrics()` | — |
| `GET /v1/config` | `getConfig()` | — |
| `PATCH /v1/config` | `patchConfig(body)` | — |
| `GET /v1/process/events` | — | — |

**Observação:** `GET /v1/process/events` não é consumido por nenhum frontend atual — é o único endpoint órfão real (ver P2-3).

---

## 4. Bugs Confirmados no Código-Fonte

Os bugs a seguir foram confirmados por leitura direta do código. Não são hipóteses.

### Bug 1 — Kelly degenera para valores enganosos com ledger vazio
**Arquivo:** `src/api/routes/risk.py:162-208`

Com zero trades no ledger (`position_closed` entries = 0):
- **Linha 176:** `win_rate = 0.5` (default hardcoded)
- **Linha 177:** `avg_win = 1.0` (default hardcoded)
- **Linha 178:** `avg_loss = 1.0` (default hardcoded)
- **Linha 182:** `full_kelly = max(0.0, 0.5 − 0.5/1.0) = 0.0`
- **Linhas 190–195:** condição `win_rate > 0 and < 1 and avg_win > 0 and avg_loss > 0` → verdadeira; `risk_of_ruin = ((0.5/0.5)^(1.0/1.0)) × 100 = 100.0`

**Resposta atual:** `{full_kelly: 0.0, fractional_kelly: 0.0, risk_of_ruin: 100.0, trades: 0}`  
**Impacto:** Operador vê "Risco de Ruína 100%" sem nenhuma operação realizada — alarme falso. A tela de Risco torna-se inoperável no estado inicial do sistema.

---

### Bug 2 — 500 em texto plano para exceções não tratadas
**Arquivo:** `src/api/main.py:103-139`

Os handlers registrados cobrem apenas:
- **Linha 103:** `RequestValidationError` → JSON 422
- **Linha 118:** `HTTPException` / `StarletteHTTPException` → JSON 4xx/5xx

Exceções Python comuns (`PermissionError`, `AttributeError`, `KeyError`, etc.) não são capturadas por nenhum handler e retornam a resposta padrão do Starlette: `500 Internal Server Error` em texto plano, sem envelope JSON.

**Exemplo concreto:** `PATCH /v1/risk/config` (`risk.py:266`) chama `_save_yaml()` (`risk.py:38-40`) que abre `_RISK_PARAMS_PATH` para escrita. Se o sistema de arquivos do container for read-only nesse ponto, uma `PermissionError` não tratada retorna 500 em texto plano.

---

### Bug 3 — `GET /v1/orders` sem paginação real
**Arquivo:** `src/api/routes/orders.py:37-46`

```python
orders = store.list(status=status, pair=pair)  # linha 42 — sem limit/offset
return APIResponse(
    data=[_order_to_out(o) for o in orders],
    meta=Meta(total=len(orders), page=1, per_page=len(orders) or 1),  # linha 45
)
```

Embora o objeto `Meta` exista, ele é preenchido com `per_page=total` — semântica de "tudo numa página". A rota aceita apenas `status` e `pair` como filtros; sem parâmetros `limit`/`offset`. Com ~10k ordens, a resposta pode atingir dezenas de MB e degradar (ou travar) o SQLite por lock WAL.

---

### Bug 4 — Schema OpenAPI inacessível em produção (nginx)
**Arquivo:** `src/api/main.py:69-77`

```python
app = FastAPI(
    docs_url="/v1/docs",
    redoc_url="/v1/redoc",
    # openapi_url NÃO definido → default FastAPI = "/openapi.json"
)
```

O FastAPI serve o schema em `/openapi.json` (sem prefixo). A página `/v1/docs` carrega o schema via fetch para `/openapi.json`. Se o nginx de produção apenas proxia `/v1/*`, a requisição a `/openapi.json` não chega ao container — `404` no browser.

`PUBLIC_PATHS` inclui `/openapi.json` (`main.py:28`), então não há bloqueio de auth — o problema é infraestrutura (nginx).

---

### Bug 5 — Sem validação de par de mercado
**Arquivo:** `src/api/routes/market.py:40-43`

```python
def _decode_pair(raw: str) -> str:
    decoded = urllib.parse.unquote(raw)
    return decoded.replace("-", "/") if "/" not in decoded else decoded
```

Qualquer string URL-decodificável é aceita como par (`BTC/USDT`, `INVALID/FOO`, `../../etc`). Sem whitelist, a exchange sintética retorna dados para qualquer símbolo passado — enganando o usuário ou causando comportamento indefinido com symbols não reconhecidos pela exchange real no futuro.

---

### Bug 6 — Jobs de backtest perdidos em restart
**Arquivo:** `src/api/routes/backtest.py:33`

```python
_jobs: Dict[str, Dict[str, Any]] = {}
```

Dicionário global em memória de módulo Python. Qualquer restart do processo API (deploy, crash, escalonamento horizontal) apaga todos os jobs em andamento e seus resultados. O cliente recebe `404` ao consultar um job que existia antes do restart, sem explicação.

---

## 5. Gaps, Inconsistências e Pontos Positivos

### 5.1 Gaps e Inconsistências por Severidade

#### 🔴 Crítico / Bloqueante para produção real

| ID | Descrição | Evidência |
|----|-----------|-----------|
| G-01 | Autenticação fail-open: sem `API_KEYS`, a API é pública | `main.py:46-48` |
| G-02 | CORS `*` por default: qualquer origem pode chamar a API | `main.py:82` |
| G-03 | `PATCH /v1/config` permite desligar `dry_run` sem auth | `config.py` + `main.py:46` |
| G-04 | Ausência de rate limiting: sem throttle em mutações ou mercado | Nenhum middleware |
| G-05 | Guardrails não eram chamados até 2026-06-04 (ADR-003): auditoria retroativa de conformidade é impossível | ADR-003 + `src/core/guardrails.py` |

#### 🟡 Importante / Deve corrigir antes de ampliar usuários

| ID | Descrição | Evidência |
|----|-----------|-----------|
| G-06 | Sem headers de segurança HTTP (CSP, HSTS, X-Frame-Options) | Nenhum middleware/nginx config no repo |
| G-07 | Kelly enganoso com ledger vazio (Bug 1 acima) | `risk.py:176-197` |
| G-08 | 500 texto plano para exceções não tratadas (Bug 2) | `main.py:103-139` |
| G-09 | `GET /v1/orders` sem paginação real (Bug 3) | `orders.py:42-45` |
| G-10 | `_jobs` backtest em memória — volátil (Bug 6) | `backtest.py:33` |
| G-11 | Cola de deploy (nginx/compose) ausente do repo — divergência código↔prod inevitável | Nenhum `infra/` no repo |

#### 🟢 Menor / Melhorias de qualidade

| ID | Descrição | Evidência |
|----|-----------|-----------|
| G-12 | Sem validação de par de mercado (Bug 5) | `market.py:40-43` |
| G-13 | `openapi.json` inacessível via nginx (Bug 4) | `main.py:70` |
| G-14 | Console React usa Babel no browser em dev (`react.development.js`) | `index.html` |
| G-15 | `GET /v1/process/events` sem consumidor conhecido | `process.py` |
| G-16 | `open_positions` fantasma não confirmado (depende de dados de prod) | — |
| G-17 | README cita "138 testes" e não documenta separação Streamlit×Console | `README.md` |

### 5.2 O Que Está Bem

O sistema tem uma base sólida para um MVP de trading:

- **Arquitetura multi-agente documentada formalmente** (ADR-002): StrategyAgent → RiskAgent → ExecutionAgent com padrões CoT, Reflection, ReAct.
- **Ledger append-only e imutável** (`TradingLedger` com JSONL): trilha de auditoria estruturada desde o início.
- **HITL workflow completo**: estados de ordem (`pending → approved/rejected/filled`), cross-process via SQLite WAL (`orders.py`, `hitl.py`).
- **Guardrails de risco implementados** (`GuardrailSystem`): limites de posição, stop-loss, risk/reward — ativos desde 2026-06-04 (ADR-003).
- **Circuit breaker e proteções de drawdown** com estados `ok/warn/paused/triggered` (`risk.py:71-154`).
- **Higiene de segredos**: `API_KEYS` via env var, `secrets.compare_digest()` timing-safe (`main.py:50`), nenhuma credencial hardcoded.
- **CI presente** (`.github/workflows/`): testes automatizados no PR.
- **ADRs formais** documentando decisões arquiteturais com critérios de transição para live.
- **Progressive Autonomy** (`hitl.py`): níveis 0-3 de autonomia configuráveis.
- **Envelope de resposta consistente** `APIResponse<T>` com `data` + `meta`: contrato de API estável.
- **Tratamento gracioso de falhas no Dashboard** (`app.py:27-48`): degrada para "API offline" sem travar.

---

## 6. Backlog de Remediação Priorizado

> Formato: `[ ]` = a fazer · `[x]` = concluído · evidência (arquivo:linha) · critério de aceite · esforço estimado (P=pequeno <4h, M=médio 4-8h, G=grande >8h).

### P0 — Segurança / Bloqueantes Pré-Produção

- [ ] **P0-0 — Verificar config real de produção** *(dev executa primeiro; destrava P0-1..P0-5)*  
  Confirmar na máquina com acesso real: `API_KEYS` setado? `EXCHANGE_DRY_RUN`? nginx proxia `/v1/*` e `/openapi.json`? Headers de resposta? Variável `CORS_ORIGINS` setada?  
  **Aceite:** relatório curto com os fatos; qualquer item aberto vira bug de P0.  
  **Esforço:** P (sondagem, não implementação)

- [ ] **P0-1 — Exigir auth em produção** (`main.py:32-59`)  
  `API_KEYS` está configurada no deploy? Se não: garantir que seja setada E documentar o processo. O middleware já implementa a lógica correta — é uma questão de configuração de infra.  
  **Aceite:** prod recusa `401 {"error":"unauthorized"}` sem `X-API-Key` em rotas não-públicas; `API_KEYS` documentada no `.env.example`.  
  **Esforço:** P (infra + doc)

- [ ] **P0-2 — Travar CORS** (`main.py:82`)  
  Setar `CORS_ORIGINS` no deploy para a origem do console React (ex.: `https://criptotrade.buildtovalue.cloud`). Sem `*` em prod.  
  **Aceite:** resposta a `OPTIONS` de origem não autorizada retorna sem `Access-Control-Allow-Origin`.  
  **Esforço:** P (variável de env + teste)

- [ ] **P0-3 — Rate limiting** (sem implementação atual)  
  Adicionar `slowapi` (ou similar) com limites distintos: mutações (`POST`, `PATCH`) e rotas de mercado (dados ao vivo) mais restritivas; leitura menos restritiva.  
  **Aceite:** burst em mutações/mercado → `429 Too Many Requests`; leitura normal não afetada; limites documentados.  
  **Esforço:** M

- [ ] **P0-4 — Proteger mutações perigosas** (`config.py`, `hitl.py`, `risk.py:242`, `agents.py`)  
  Rotas `PATCH /v1/config` (desliga `dry_run`), `PATCH /v1/hitl/config` (autonomia=3), `PATCH /v1/risk/config`, `PATCH /v1/agents/{id}/config` devem exigir auth independentemente de `API_KEYS` estar setado (considerar escopo adicional). Alterar `dry_run=false` pode exigir confirmação explícita/flag no body.  
  **Aceite:** inacessíveis sem `X-API-Key` válida; `dry_run=false` exige campo `confirm: true` no body.  
  **Esforço:** M

- [ ] **P0-5 — Headers de segurança HTTP**  
  No nginx e/ou middleware FastAPI: `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Referrer-Policy: strict-origin`.  
  **Aceite:** headers presentes em toda resposta; verificado via `curl -I`.  
  **Esforço:** P (nginx config)

---

### P1 — Correção / Confiabilidade (Confirmados no Código)

- [ ] **P1-1 — Handler catch-all `Exception` → JSON 500** (`main.py:103-139`)  
  Adicionar `@app.exception_handler(Exception)` que retorne `{"error": "internal_error", "message": "Erro interno inesperado.", "docs": "/v1/docs"}` com status 500. Logar o traceback internamente (sem expô-lo ao cliente).  
  **Aceite:** qualquer exceção Python não tratada retorna JSON 500, nunca texto plano; stacktrace aparece nos logs do container, não na resposta HTTP.  
  **Esforço:** P

- [ ] **P1-2 — Corrigir `PATCH /v1/risk/config` em FS read-only** (`risk.py:38-40`, `risk.py:247-267`)  
  `_save_yaml()` abre `_RISK_PARAMS_PATH` para escrita sem tratar `PermissionError` ou `FileNotFoundError`. Resolver: (a) tratar exceção e retornar `503 {"error":"config_not_writable"}` estruturado, ou (b) mover config para banco de dados/variável de ambiente.  
  **Aceite:** `PATCH /v1/risk/config` em container read-only retorna 4xx/5xx estruturado JSON, não plain-text 500; + teste unitário cobrindo o caso de falha de escrita.  
  **Esforço:** M

- [ ] **P1-3 — Paginar `GET /v1/orders`** (`orders.py:37-46`)  
  Adicionar parâmetros `limit: int = Query(50, ge=1, le=500)` e `offset: int = Query(0, ge=0)`. Atualizar `store.list()` para aceitar `limit`/`offset`. Atualizar `Meta` com `page` calculado. Atualizar Console React e Streamlit para consumir paginação.  
  **Aceite:** `GET /v1/orders?limit=50&offset=0` retorna ≤ 50 ordens + `Meta` correto; com ~10k ordens, resposta < 1s e sem crescimento de memória; console e dashboard paginam.  
  **Esforço:** M

- [ ] **P1-4 — Kelly com dados insuficientes** (`risk.py:162-208`)  
  Se `trades == 0` (ou `trades < N`, ex. 10), retornar estado `insufficient_data` em vez de calcular com defaults enganosos. Sugestão: adicionar campo `data_quality: "ok" | "insufficient"` em `KellyOut`; quando insuficiente, `full_kelly=null`, `risk_of_ruin=null`.  
  **Aceite:** `GET /v1/risk/kelly` com ledger vazio retorna `{data_quality: "insufficient", trades: 0, full_kelly: null, risk_of_ruin: null}`; tela de Risco exibe "Dados insuficientes (0 trades)" em vez de "Risco 100%".  
  **Esforço:** P

- [ ] **P1-5 — Investigar `open_positions` fantasma** (a confirmar em P0-0)  
  Mapear ciclo completo: `position_opened` → `position_closed` no ledger; verificar se ordens sintéticas são fechadas corretamente pelo orquestrador. Requer dados de prod (P0-0).  
  **Aceite:** contador `open_positions` reflete posições reais; sem crescimento ilimitado entre restarts; teste de integração cobrindo o ciclo completo.  
  **Esforço:** G (investigação + fix dependente de dados de prod)

- [ ] **P1-6 — `openapi_url` para o prefixo `/v1`** (`main.py:70-77`)  
  Opção A (mais simples): setar `openapi_url="/v1/openapi.json"` em `create_app()` e adicionar `/v1/openapi.json` em `PUBLIC_PATHS`.  
  Opção B: configurar nginx para proxiar também `/openapi.json`.  
  **Aceite:** `/v1/docs` carrega o schema sem erro 404 em produção; `/v1/redoc` funciona igualmente.  
  **Esforço:** P

- [ ] **P1-7 — Conflito de preço no Console React** (`docs/design/pages/screen_market.jsx`)  
  Header do console usa dado mock/hardcoded enquanto gráfico busca da API — fonte dupla. Unificar: header lê o mesmo dado do `apiClient.js`.  
  **Aceite:** preço no header == último candle do gráfico; sem discrepância visual.  
  **Esforço:** P

---

### P2 — Produto / Conectar Backend Existente

- [ ] **P2-1 — Persistir jobs de backtest** (`backtest.py:33`)  
  Substituir `_jobs: Dict` por persistência em SQLite (tabela `backtest_jobs`) ou Redis. Mínimo viável: SQLite com `CREATE TABLE IF NOT EXISTS backtest_jobs (id TEXT PRIMARY KEY, status TEXT, result TEXT, error TEXT, created_at TEXT, completed_at TEXT)`.  
  **Aceite:** job sobrevive a restart do processo API; múltiplos workers não perdem estado; `GET /v1/backtest/jobs/{id}` retorna `404` estruturado para job inexistente.  
  **Esforço:** M

- [ ] **P2-2 — Validar par de mercado** (`market.py:40-43`)  
  Implementar allowlist de símbolos configurável (carregada de env var ou YAML, ex.: `ALLOWED_PAIRS=BTC/USDT,ETH/USDT,SOL/USDT`). `_decode_pair()` valida contra a lista e lança `HTTPException(422)` para símbolo não autorizado.  
  **Aceite:** `GET /v1/market/INVALID/candles` → `422 {"error":"invalid_pair"}`; `BTC/USDT` (e `BTC-USDT`) → dados normais; allowlist documentada.  
  **Esforço:** P

- [ ] **P2-3 — Definir destino de `GET /v1/process/events`** (`src/api/routes/process.py`)  
  Único endpoint sem consumidor frontend conhecido. Duas opções:  
  (a) Expor no Console React como "Export de Eventos XES" (Process Mining);  
  (b) Documentar como API de integração externa apenas, com nota no README.  
  **Aceite:** endpoint tem destino explícito documentado; se exposto no console, existe botão de download.  
  **Esforço:** P (decisão de PM) a M (se implementar no console)

- [ ] **P2-4 — Formalizar Streamlit (dev-tool) × Console React (produção) no README** (`README.md`)  
  Atualizar README para: (a) distinguir claramente os dois frontends e seus propósitos; (b) corrigir contagem de testes (verificar número real vs "138"); (c) documentar como rodar cada frontend.  
  **Aceite:** README condiz com a realidade; novo dev entende em < 5 min qual frontend usar em cada contexto.  
  **Esforço:** P

---

### P3 — Build / Infra / Qualidade

- [ ] **P3-1 — Build de produção do Console React** (`docs/design/pages/index.html`)  
  **Opção A (Vite):** adicionar `package.json` + `vite.config.ts`; build gera `dist/` minificado; nginx serve static. Mais robusto, requer configurar CI.  
  **Opção B (Import Map ESM):** trocar `react.development.js` + Babel-no-browser por import map com versões ESM minificadas fixas (`esm.sh` ou CDN versionado). Zero toolchain, mas depende de CDN externo.  
  **Tradeoff:** Opção A = zero dependência de CDN em runtime, mais complexo. Opção B = simples, mas CDN é ponto de falha/supply chain.  
  **Aceite:** prod serve JS minificado, sem transpile no browser; LCP melhora; nenhum `react.development.js` em prod.  
  **Esforço:** M (A) ou P (B)

- [ ] **P3-2 — Versionar cola de deploy** (nginx + compose ausentes do repo)  
  Criar `infra/docker-compose.prod.yml` e `infra/nginx.conf` com: proxy `/v1/*` → API, `/openapi.json` → API, servir static do console, gzip, timeouts, headers de segurança.  
  **Aceite:** `infra/` no repo; `README` explica como deployer; divergência código↔prod torna-se auditável.  
  **Esforço:** M

- [ ] **P3-3 — Monitoramento de erros (Sentry)** (API + Console React)  
  Integrar Sentry SDK: Python para a API (captura 5xx + unhandled exceptions), JS para o console (captura erros de UI).  
  **Aceite:** erros 5xx aparecem no Sentry com contexto; alertas configurados para erros novos.  
  **Esforço:** P

- [ ] **P3-4 — Cliente tipado gerado do OpenAPI** (Console React)  
  Usar `openapi-typescript` ou `orval` para gerar tipos TypeScript a partir do `/v1/openapi.json`. Substituir chamadas manuais em `apiClient.js` pelo cliente gerado.  
  **Aceite:** drift de contrato (ex.: par `/`↔`-`) detectado em build; nenhuma string de endpoint manual no frontend.  
  **Esforço:** M

- [ ] **P3-5 — Ampliar cobertura de testes**  
  (a) Testes por-endpoint da API: arquivo de teste por rota (`test_orders.py`, `test_risk.py`, etc.) — hoje ~1 arquivo para ~37 endpoints.  
  (b) E2E com Playwright: console React — paginação de ordens, preço consistente, Kelly sem dados, fluxo HITL.  
  (c) Testes unitários para `strategies/`, `chains/`, `memory/`.  
  **Aceite:** gate de cobertura mínima (ex. 80%); E2E no CI; nenhuma rota sem teste de contrato.  
  **Esforço:** G

- [ ] **P3-6 — Pipeline de deploy automatizado**  
  CI/CD: no merge em `main`, deploy automático com validação de config pré-deploy (assert `API_KEYS` setado, `CORS_ORIGINS` não é `*`, `dry_run` intencional e documentado).  
  **Aceite:** deploy no merge; falha se config insegura; história de deploys auditável.  
  **Esforço:** G

---

## 7. Modelo de Coordenação e Próximos Passos

### 7.1 Papéis

| Papel | Responsabilidade |
|-------|-----------------|
| **Coordenador** (este agente) | Mantém este documento versionado; prioriza backlog; revisa PRs do dev via `/code-review`; atualiza checkboxes conforme conclusão |
| **Dev** | Implementa item a item; abre PR contra `claude/youthful-gauss-r1fdwb` (ou branch derivada); não muda o documento de coordenação |
| **Fonte de verdade do progresso** | Checkboxes neste arquivo (versionado em git) |

### 7.2 Sequência Recomendada

```
P0-0 (verificar prod)
  ↓ resultados informam
P0-1 + P0-2 (auth + CORS) → P0-3 (rate limit) → P0-4 (proteger mutações) → P0-5 (headers)
  ↓ segurança resolvida
P1-1 (catch-all exception) → P1-4 (Kelly) → P1-6 (openapi_url) → P1-3 (paginação) → P1-2 (save_yaml)
  ↓ confiabilidade
P2-2 (validar par) → P2-4 (README) → P2-1 (persistir jobs) → P2-3 (process/events)
  ↓ produto
P3-2 (infra/cola) → P3-1 (build) → P3-3 (Sentry) → P3-5 (testes) → P3-4 (cliente tipado) → P3-6 (CI/CD)
```

### 7.3 Critério de "Pronto para Live" (ADR-001 + gaps de segurança)

Além dos critérios do ADR-001 (Sharpe > 1.5, DD < 10%, Win Rate > 55%, 100 trades mínimos), os seguintes itens de segurança são **pré-requisitos técnicos** independentes de performance:

- [ ] P0-1: auth habilitada em prod
- [ ] P0-2: CORS travado
- [ ] P0-3: rate limiting ativo
- [ ] P0-4: mutações perigosas protegidas
- [ ] P0-5: headers de segurança presentes
- [ ] P1-1: sem 500 texto plano
- [ ] P3-2: cola de deploy versionada (rastreabilidade)

---

## 8. Anexos

### Anexo A — Comandos de Sondagem (Executar do Host com Acesso à Produção)

Execute estes comandos de uma máquina com acesso a `https://criptotrade.buildtovalue.cloud/` para confirmar ou refutar os achados de P0-0:

```bash
# A. Verificar se API está aberta (sem API_KEYS)
curl -s https://criptotrade.buildtovalue.cloud/v1/metrics | jq .

# B. Verificar CORS
curl -si -X OPTIONS https://criptotrade.buildtovalue.cloud/v1/metrics \
  -H "Origin: https://evil.com" \
  -H "Access-Control-Request-Method: GET" | grep -i "access-control"

# C. Verificar openapi.json
curl -si https://criptotrade.buildtovalue.cloud/openapi.json | head -5
curl -si https://criptotrade.buildtovalue.cloud/v1/openapi.json | head -5

# D. Verificar headers de segurança
curl -si https://criptotrade.buildtovalue.cloud/health | grep -iE "x-frame|x-content|strict-transport|content-security"

# E. Verificar Kelly com ledger vazio (ou pouco preenchido)
curl -s https://criptotrade.buildtovalue.cloud/v1/risk/kelly | jq .data

# F. Verificar paginação de ordens
curl -s "https://criptotrade.buildtovalue.cloud/v1/orders" | jq '.meta'

# G. Verificar 500 texto plano (forçar erro de escrita)
curl -s -X PATCH https://criptotrade.buildtovalue.cloud/v1/risk/config \
  -H "Content-Type: application/json" \
  -d '{"max_position_size_pct": 99.9}' | head -20

# H. Verificar dry_run e config atual
curl -s https://criptotrade.buildtovalue.cloud/v1/config | jq .

# I. Verificar open_positions (possível fantasma)
curl -s https://criptotrade.buildtovalue.cloud/v1/metrics | jq '.data.open_positions'

# J. Verificar process/events
curl -si https://criptotrade.buildtovalue.cloud/v1/process/events | head -5
```

### Anexo B — Mapa Rápido de Criticidade por Arquivo

| Arquivo | Criticidade | Itens do backlog |
|---------|-------------|-----------------|
| `src/api/main.py` | 🔴 Alta | P0-1, P0-2, P0-4, P1-1, P1-6 |
| `src/api/routes/risk.py` | 🟡 Média | P1-2, P1-4 |
| `src/api/routes/orders.py` | 🟡 Média | P1-3 |
| `src/api/routes/backtest.py` | 🟡 Média | P2-1 |
| `src/api/routes/market.py` | 🟢 Baixa | P2-2 |
| `src/api/routes/config.py` | 🔴 Alta | P0-4 |
| `src/api/routes/process.py` | 🟢 Baixa | P2-3 |
| `docs/design/pages/` | 🟡 Média | P1-7, P3-1, P3-4 |
| `infra/` (ausente) | 🔴 Alta | P0-5, P3-2, P3-6 |
| `README.md` | 🟢 Baixa | P2-4 |

---

*Documento mantido pelo Coordenador. Para atualizar checkboxes: editar este arquivo e fazer commit/push na branch de trabalho. Para implementações: abrir PR contra `claude/youthful-gauss-r1fdwb`.*
