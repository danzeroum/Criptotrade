# Pendências do Dono — v1 (execução do roadmap v1)

> Itens que dependem de **decisão ou credencial do dono**. O agente implementou
> tudo que conseguiu sem esses acessos e seguiu para a próxima tarefa.
> Ver também `docs/acaoPendenteDono.md` (deploy/TLS/Sentry herdados).
> Atualizado: 2026-06-20.

## 🔑 Credenciais / configuração

- [ ] **Ativar a camada de IA (LLM).** O código está pronto e **desligado por
  padrão**. Para ligar em runtime:
  - `LLM_ENABLED=true`
  - `LLM_PROVIDER=google` (padrão) · `deepseek` · `openai` · `anthropic`
  - chave correspondente: `GOOGLE_API_KEY` (Gemini), `DEEPSEEK_API_KEY`,
    `OPENAI_API_KEY`, ou `ANTHROPIC_API_KEY`
  - opcional: `LLM_MODEL` (default por provider).
  - Sem chave/flag, o pipeline roda determinístico (sem rede), como hoje.
  - **Deps**: Gemini e DeepSeek/OpenAI já estão pinados (`langchain-google-genai`,
    `langchain-openai`); só `anthropic` exige `langchain-anthropic` (não pinado).

- [ ] **Escolha do provider de LLM.** Default = **Gemini** (deps já presentes).
  DeepSeek e OpenAI também prontos (`langchain-openai` pinado); Claude exige a
  lib correspondente. Setar `LLM_PROVIDER`. Decisão de custo/qualidade do dono.

## 🟠 Decisões de produto

- [ ] **Ir a "preço real + execução paper".** Agora é um modo de 1ª classe:
  `EXCHANGE_DRY_RUN=false` (dados reais via ccxt) + `ORDER_ROUTING=paper` (default).
  Requer rede liberada para a exchange. **Validar** com a stack antes de usar.

- [ ] **Ir a LIVE (ordens reais).** `ORDER_ROUTING=live` + `EXCHANGE_DRY_RUN=false`
  + credenciais da exchange (`EXCHANGE_API_KEY/SECRET`). Decisão deliberada e de
  alto risco — **não** ligar junto com o deploy. Antes disso, cumprir os
  critérios de go-live do ADR-001 (Sharpe>1.5, 100+ trades, etc.), que hoje não
  são atingíveis em dados sintéticos.

## ⏭️ Itens adiados que dependem do acima

- [ ] **WebSocket de preços live (CT-012 / B1).** Só faz sentido com
  `ORDER_ROUTING=live`/dados reais + rede. Implementação adiada até a decisão de
  ir a real; anotado no roadmap.

## ❌ Descartados (decisão de produto)

- **A8 — Faturamento & Uso: DESCARTADO** (decisão do PM, jul/2026). A
  plataforma é de uso pessoal, não SaaS — não há cobrança, planos ou medição
  de uso a construir. Removido das pendências; o card permanece no handoff
  apenas como registro histórico.

## ℹ️ Herdados (já documentados em `docs/acaoPendenteDono.md`)
- DNS + portas 80/443, `API_KEYS` forte, certificado Let's Encrypt, `SENTRY_DSN`,
  secrets de deploy (CD). Sem mudança nesta v1.
