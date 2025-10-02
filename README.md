# 🤖 Crypto AI Trading Platform

> **Plataforma de trading automatizada de criptomoedas com IA, priorizando segurança e gestão de risco.**

[![BuildToValue](https://img.shields.io/badge/BuildToValue-v6.1-blue)](https://buildtovalue.com)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Status](https://img.shields.io/badge/Status-MVP-orange)](https://github.com)

---

## 📋 Visão Geral

Este projeto implementa um sistema de trading automatizado usando **agentes de IA especializados** que colaboram para:

- 📊 **Analisar** mercados e gerar sinais de trading
- ⚖️ **Validar** sinais contra regras rigorosas de gestão de risco
- 💼 **Executar** ordens de forma segura e auditável
- 🔒 **Garantir** que o capital seja sempre protegido

### 🎯 Objetivos do MVP

- ✅ **Paper Trading**: Validar estratégias sem risco real
- ✅ **Safety First**: Guardrails e HITL em todas as operações
- ✅ **Auditável**: Ledger imutável de todas as decisões
- ✅ **Baixo Custo**: Infra < $200/mês para operação solo

---

## 🏗️ Arquitetura

### Multi-Agent System

```
┌─────────────────────────────────────────────────────────┐
│              Squad Orchestrator                         │
│         (Coordena os agentes especializados)            │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │  Strategy  │  │    Risk    │  │ Execution  │
   │   Agent    │─▶│   Agent    │─▶│   Agent    │
   │            │  │            │  │            │
   │ CoT        │  │ Reflection │  │ ReAct      │
   └────────────┘  └────────────┘  └────────────┘
          │               │               │
          │               ▼               │
          │         ┌──────────┐          │
          │         │Guardrails│          │
          │         └──────────┘          │
          │                               │
          └───────────────┬───────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ Trading Ledger│
                  │  (Audit Trail)│
                  └───────────────┘
```

### Componentes Principais

| Componente | Responsabilidade | Pattern |
|------------|------------------|---------|
| **StrategyAgent** | Análise técnica e geração de sinais | Chain-of-Thought |
| **RiskAgent** | Validação contra regras de risco | Reflection |
| **ExecutionAgent** | Execução de ordens na exchange | ReAct Loop |
| **Guardrails** | Bloqueio de operações perigosas | Validation Rules |
| **TradingLedger** | Registro imutável de decisões | Append-Only Log |

---

## 🚀 Quick Start

### Pré-requisitos

- Python 3.11+
- Docker & Docker Compose
- API keys (Gemini Pro e exchange)

### Instalação (< 5 minutos)

```bash
# 1. Clone o repositório
git clone https://github.com/yourusername/crypto-ai-trader.git
cd crypto-ai-trader

# 2. Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas API keys

# 3. Instale dependências
pip install -r requirements.txt

# 4. (Opcional) Use Docker
docker-compose up -d

# 5. Execute testes
pytest tests/ -v

# 6. Inicie o dashboard
streamlit run src/dashboard/app.py
```

### Primeira Execução

```python
from src.orchestration.squad_orchestrator import SquadOrchestrator
from src.core.exchange_client import ExchangeClient

# Inicializa em modo paper trading
exchange = ExchangeClient(testnet=True)
squad = SquadOrchestrator(exchange)

# Analisa e (potencialmente) executa trade
result = await squad.analyze_and_trade(
    symbol="BTC/USDT",
    timeframe="1h"
)

print(result)
```

---

## 🔒 Segurança

### Guardrails Ativos

- ✅ **Position Size Limit:** Máximo 5% do portfólio por trade
- ✅ **Stop Loss Obrigatório:** Sempre presente, máximo -3% por trade
- ✅ **Daily Loss Limit:** Máximo -5% do portfólio por dia
- ✅ **Concurrent Positions:** Máximo 3 trades simultâneos
- ✅ **API Key Protection:** Nunca em código, sempre em env vars
- ✅ **Sandbox Mode:** Todas as estratégias executam em ambiente isolado
- ✅ **HITL Approval:** Humano aprova TODA ordem antes da execução (L1 autonomy)

### Ledger de Auditoria

Todas as decisões são registradas em `.buildtovalue/ledger/trades.jsonl`:

```json
{
  "timestamp": "2025-10-02T15:30:00Z",
  "event_type": "signal_generated",
  "data": {
    "agent": "strategy",
    "signal": {...},
    "confidence": 0.75
  }
}
```

---

## 📊 Métricas de Sucesso

### Critérios para Transição (Paper → Live)

**Obrigatórios (TODOS devem ser atendidos):**
- ✅ Sharpe Ratio > 1.5 (3 meses)
- ✅ Max Drawdown < 10%
- ✅ Win Rate > 55% (100+ trades)
- ✅ Zero violações de guardrails (1 mês)
- ✅ Uptime > 99.5% (1 mês)

**Métricas Atuais (MVP):**
- 🟡 **Status:** Paper Trading
- 🟡 **Trades Executados:** 0
- 🟡 **Sharpe Ratio:** N/A
- 🟡 **Drawdown:** N/A

---

## 📁 Estrutura do Projeto

```
crypto-ai-trader/
├── .buildtovalue/          # BuildToValue artifacts
│   ├── consensus/          # Discovery & decision tree
│   ├── ledger/             # Audit trail
│   └── prompts/            # Prompt registry
├── src/
│   ├── agents/             # Strategy, Risk, Execution agents
│   ├── core/               # Config, ledger, exchange client
│   ├── safety/             # Guardrails, sandbox, security
│   ├── strategies/         # Trading strategies (DCA, etc)
│   ├── tools/              # Market data, indicators
│   ├── orchestration/      # Squad orchestrator
│   └── dashboard/          # Streamlit UI
├── tests/                  # Unit, integration, emergent tests
├── docs/                   # ADRs, tutorials
├── config/                 # Agent constitution, risk params
└── scripts/                # Setup, validation, backtest
```

---

## 🧪 Testes

```bash
# Todos os testes
pytest tests/ -v --cov=src

# Testes específicos
pytest tests/unit/test_agents.py -v
pytest tests/unit/test_guardrails.py -v
pytest tests/integration/test_trading_flow.py -v

# Testes de comportamento emergente
pytest tests/emergent/ -v
```

### Cobertura Esperada
- Unit tests: > 80%
- Integration tests: > 60%
- Critical paths: 100%

---

## 📚 Documentação

### ADRs (Architecture Decision Records)

- [ADR-001: Paper Trading First](docs/ADR/001-paper-trading-first.md) ✅
- [ADR-002: Multi-Agent Architecture](docs/ADR/002-agent-architecture.md) ✅
- ADR-003: Risk Management Strategy (TODO)

### Tutoriais

- [Getting Started](docs/tutorials/getting_started.md) (TODO)
- [Adding a New Strategy](docs/tutorials/new_strategy.md) (TODO)
- [Understanding Guardrails](docs/tutorials/guardrails.md) (TODO)

### Metodologia

Este projeto segue **BuildToValue v6.1** com modo AI Agent:
- [Discovery Consensus](/.buildtovalue/consensus/discovery-consensus.v6.json)
- [Decision Tree](/.buildtovalue/consensus/decision-tree-pro.v6.json)
- [Agent Constitution](/config/agents/constitution.yaml)

---

## 🛠️ Configuração

### Parâmetros de Trading (config/strategies/risk_params.yaml)

```yaml
risk_management:
  max_position_size_pct: 5.0
  stop_loss_pct: 3.0
  max_daily_loss_pct: 5.0
  max_concurrent_positions: 3
  
execution:
  paper_trading: true
  exchange: binance
  testnet: true
  
autonomy:
  level: 1  # L1: HITL approval required
  hitl_approval_required: true
```

### Limites de Recursos (src/core/config.py)

```python
MAX_TOKENS_PER_INTERACTION = 8000
MAX_API_COST_PER_TASK = 0.05  # $0.05
TIMEOUT_SECONDS = 30
MAX_CONCURRENT_ANALYSIS = 3
```

---

## 🔄 Roadmap

### ✅ Fase 1: MVP (Semanas 1-6)
- [x] Estrutura base do projeto
- [x] Agentes fundamentais (Strategy, Risk, Execution)
- [x] Sistema de guardrails
- [x] Ledger de auditoria
- [x] Paper trading mode
- [ ] Dashboard básico (Streamlit)
- [ ] Estratégia DCA Otimizado
- [ ] Testes unitários completos
- [ ] Documentação inicial

### 🔄 Fase 2: Melhorias (Semanas 7-12)
- [ ] Estratégias adicionais (Grid, Momentum)
- [ ] Sistema de backtesting
- [ ] Progressive Autonomy (L1→L2)
- [ ] RAG para contexto de mercado
- [ ] WebSocket para dados real-time
- [ ] Alertas via Telegram
- [ ] Métricas avançadas (Prometheus)

### 🚀 Fase 3: Live Trading (Mês 4+)
- [ ] Validação completa em paper trading
- [ ] Testes de penetração (security)
- [ ] Auditoria de código externo
- [ ] Seguro/stop-loss de portfólio
- [ ] Migração gradual para live trading
- [ ] Monitoramento 24/7

---

## 💰 Custos Estimados

### MVP (Paper Trading)
- **Infraestrutura:** $0 (local) ou $40-60/mês (VPS)
- **API Costs (AI):** $50-100/mês (Gemini Pro + backup GPT)
- **Backup Storage:** $5/mês
- **TOTAL:** **$55-165/mês**

### Live Trading (Futuro)
- **Infraestrutura:** $100-200/mês
- **API Costs:** $100-200/mês
- **Seguro/Monitoramento:** $50/mês
- **TOTAL:** **$250-450/mês**

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/amazing`)
3. Commit suas mudanças (`git commit -m 'feat: add amazing feature'`)
4. Push para a branch (`git push origin feature/amazing`)
5. Abra um Pull Request

### Padrões de Commit

Seguimos [Conventional Commits](https://conventionalcommits.org/):
- `feat:` nova funcionalidade
- `fix:` correção de bug
- `docs:` documentação
- `test:` testes
- `refactor:` refatoração de código

---

## 📞 Suporte

- 📧 **Email:** support@example.com
- 💬 **Discord:** [Join our server](#)
- 📖 **Docs:** [Full documentation](#)
- 🐛 **Issues:** [GitHub Issues](https://github.com/yourusername/crypto-ai-trader/issues)

---

## ⚠️ Disclaimer

**IMPORTANTE:** Este software é fornecido "como está", sem garantias de qualquer tipo. Trading de criptomoedas envolve risco substancial de perda. Nunca invista mais do que você pode perder. Este projeto está em fase MVP e deve ser usado apenas para fins educacionais e de pesquisa.

**Não somos consultores financeiros.** Faça sua própria pesquisa (DYOR) e consulte profissionais antes de tomar decisões de investimento.

---

## 📄 Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

---

## 🙏 Agradecimentos

- [BuildToValue](https://buildtovalue.com) - Metodologia de desenvolvimento
- [LangChain](https://langchain.com) - Framework de agentes
- [CCXT](https://ccxt.com) - Exchange connectivity
- Comunidade Open Source

---

**Desenvolvido com 🤖 seguindo BuildToValue v6.1 - AI Agent Mode**

*"Disciplina mínima, valor máximo, segurança sempre."*
