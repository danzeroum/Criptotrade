# ADR-002: Multi-Agent Architecture

## Status
✅ **Aceita** (2025-10-02)

## Contexto
Precisamos definir como organizar a lógica de trading do sistema. Principais questões:
- Como separar responsabilidades (análise vs execução vs risco)?
- Como garantir que cada decisão seja validada antes da execução?
- Como manter auditoria completa de todas as decisões?
- Como evoluir o sistema de forma modular?

## Decisão
**Adotar arquitetura Multi-Agent com 3 agentes especializados orquestrados por um Squad Orchestrator.**

### Agentes Especializados

#### 1. **StrategyAgent** (Analista)
- **Responsabilidade:** Gerar sinais de trading baseados em análise técnica
- **Pattern:** Chain-of-Thought reasoning
- **Ferramentas:** Market data, technical indicators, pattern recognition
- **Output:** Signal com confidence score

#### 2. **RiskAgent** (Auditor)
- **Responsabilidade:** Validar sinais contra regras de gestão de risco
- **Pattern:** Reflection (validate → reflect → refine)
- **Ferramentas:** Portfolio analyzer, risk calculator, guardrails
- **Output:** Approved/Rejected com justificativa

#### 3. **ExecutionAgent** (Executor)
- **Responsabilidade:** Executar ordens validadas na exchange
- **Pattern:** ReAct (Thought → Action → Observation)
- **Ferramentas:** Exchange API, order management
- **Output:** Order confirmation ou erro

### SquadOrchestrator
- **Responsabilidade:** Coordenar os 3 agentes em sequência
- **Pattern:** Chaining + HITL
- **Fluxo:** Strategy → Risk → HITL → Execution
- **Logging:** Ledger imutável de todas as etapas

## Alternativas Consideradas

### 1. **Monolito Simples**
```python
def analyze_and_trade(symbol):
    signal = generate_signal(symbol)
    if validate_risk(signal):
        execute_order(signal)
```
- **Prós:** Simplicidade, menos overhead
- **Contras:** 
  - Difícil de testar componentes isolados
  - Impossível evoluir partes independentemente
  - Sem auditoria granular
  - Não segue padrões agênticos da metodologia
- **Rejeição:** Não escalável e não alinhado com BuildToValue v6.1

### 2. **Pipeline Linear Sem Agentes**
```python
signal = market_analysis_pipeline(symbol)
validated_signal = risk_pipeline(signal)
order = execution_pipeline(validated_signal)
```
- **Prós:** Simples, funcional para MVP
- **Contras:**
  - Sem reasoning explícito
  - Difícil adicionar novos padrões (routing, memory)
  - Não aproveita capacidades de LLMs
- **Rejeição:** Subutiliza potencial de IA agêntica

### 3. **Multi-Agent → Escolhida**
- **Prós:**
  - Separação clara de responsabilidades (SRP)
  - Cada agente pode evoluir independentemente
  - Auditoria granular de decisões
  - Facilita testes unitários por agente
  - Alinhado com padrões BuildToValue (CoT, Reflection, ReAct)
  - Permite adicionar novos agentes no futuro (BacktestAgent, PortfolioAgent)
- **Contras:**
  - Mais complexidade inicial
  - Overhead de orquestração
- **Mitigações:**
  - Usar abstrações (BaseAgent) para reduzir boilerplate
  - SquadOrchestrator encapsula complexidade

## Diagrama de Fluxo

```
┌─────────────────────────────────────────────────────────┐
│                  SquadOrchestrator                      │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │  Strategy  │  │    Risk    │  │ Execution  │
   │   Agent    │─▶│   Agent    │─▶│   Agent    │
   └────────────┘  └────────────┘  └────────────┘
          │               │               │
   [Chain-of-      [Reflection]    [ReAct Loop]
    Thought]              │               │
          │               ▼               ▼
          │         ┌──────────┐    ┌──────────┐
          │         │Guardrails│    │ Exchange │
          │         └──────────┘    └──────────┘
          │               │               │
          └───────────────┴───────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │ Trading Ledger│
                  └───────────────┘
```

## Padrões de Reasoning por Agente

### StrategyAgent - Chain-of-Thought
```
1. Identify market context (trend, volatility, momentum)
2. Calculate technical indicators (RSI, MACD, BB)
3. Evaluate pattern signals (support/resistance, breakouts)
4. Synthesize into trading signal (action, entry, targets)
5. Assign confidence score based on alignment
```

### RiskAgent - Reflection
```
1. Initial Validation (check against hard limits)
2. Reflection (did I miss hidden risks?)
3. Refinement (adjust confidence, add warnings)
4. Final Decision (approve/reject with reasoning)
```

### ExecutionAgent - ReAct
```
THOUGHT: Need to execute BUY order for BTC/USDT
ACTION: Place limit order at $45,000
OBSERVATION: Order placed successfully, order_id=12345
THOUGHT: Monitor for fill
ACTION: Check order status
OBSERVATION: Order filled at $45,001
```

## Comunicação Entre Agentes

### Protocol
```python
# StrategyAgent output
{
  "signal": {
    "action": "BUY",
    "symbol": "BTC/USDT",
    "entry_price": 45000,
    "stop_loss": 43500,
    "take_profit": 48000,
    "position_size_pct": 3.0
  },
  "confidence": 0.75,
  "reasoning": "Bullish breakout above resistance..."
}

# RiskAgent output
{
  "approved": True,
  "validation": {
    "issues": [],
    "warnings": ["Wide stop loss"],
    "confidence": 0.85
  },
  "reasoning": "Signal passes all risk checks..."
}

# ExecutionAgent output
{
  "success": True,
  "order_id": "PAPER_abc123",
  "status": "filled",
  "confidence": 1.0
}
```

### Handoffs
1. **Strategy → Risk:** Signal dictionary com reasoning
2. **Risk → Execution:** Validated signal + approval flag
3. **Execution → Ledger:** Complete trade record

## Consequências

### Positivas
- ✅ Responsabilidades bem definidas (SRP)
- ✅ Cada agente pode usar padrão de reasoning mais adequado
- ✅ Fácil adicionar novos agentes (PortfolioAgent, NewsAgent)
- ✅ Testes isolados por agente
- ✅ Auditoria granular via ledger
- ✅ Alinhado com BuildToValue v6.1 Multi-Agent Collaboration

### Negativas
- ⚠️ Overhead de orquestração (~50-100ms por trade)
- ⚠️ Mais arquivos e abstrações para manter
- ⚠️ Curva de aprendizado para novos desenvolvedores

### Mitigações
- Documentar bem as interfaces (BaseAgent, task/result schemas)
- Criar diagramas de fluxo (Mermaid no README)
- Overhead aceitável dado timeline de trading (~seconds)
- Testes automatizados garantem integração

## Evolução Futura

### Fase 2 (Nice-to-Have)
- **PortfolioAgent:** Gerenciar carteira completa e diversificação
- **NewsAgent:** Análise de sentimento de notícias
- **BacktestAgent:** Validar estratégias com dados históricos

### Fase 3 (Enterprise)
- **SupervisorAgent:** Meta-coordenação de múltiplas strategies
- **LearningAgent:** Ajustar parâmetros com RLHF
- **RegulatoryAgent:** Compliance com regulações financeiras

## Validação

- [x] Arquiteto aprovou (confidence 0.95)
- [x] Developer aprovou (confidence 0.9)
- [x] Auditor aprovou (confidence 0.85) - "Separação facilita audit"
- [x] Consenso: Unânime

## Referências
- BuildToValue v6.1 - Multi-Agent Collaboration pattern
- LangChain Multi-Agent Systems
- ReAct Paper: https://arxiv.org/abs/2210.03629
- Chain-of-Thought: https://arxiv.org/abs/2201.11903

---
**Última Atualização:** 2025-10-02  
**Próxima Revisão:** Após implementação dos 3 agentes base
