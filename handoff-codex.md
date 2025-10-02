# 🚀 HANDOFF PARA CODEX - Crypto AI Trading Platform v0.1.0-alpha

## 📋 CONTEXTO

**Stage:** 01_BRIEF + 02_CODE (Inicialização)  
**Project Type:** AI Agent System  
**Foundation Level:** lite  
**Timeline:** 4-6 semanas para MVP  
**Budget:** < $200/mês operacional  

### Trajetória Anterior
- ✅ Discovery consensus validado
- ✅ Decision tree aprovado por unanimidade (confidence 0.9)
- ✅ Arquitetura de agentes definida (Strategy + Risk + Execution)
- 🎯 **PRÓXIMO:** Implementar estrutura base do projeto

---

## 📊 INFORMAÇÕES

### Padrões Agênticos Disponíveis
1. **Prompt Chaining** (P0) - Market analysis → Signal → Risk assessment
2. **Routing** (P0) - Market condition classification
3. **Tool Use** (P0) - Exchange API integration
4. **Reasoning Techniques** (P0) - CoT para trade decisions
5. **Guardrails** (P0) - Order validation & limits
6. **Memory Management** (P1) - Trade history & patterns
7. **Multi-Agent Collaboration** (P1) - Squad coordination

### Tools Autorizados
- ✅ `ccxt` - Exchange connectivity (read-only em MVP)
- ✅ `ta-lib` / `pandas-ta` - Technical indicators
- ✅ `langchain` - Agent orchestration
- ✅ `chromadb` - Vector store para RAG
- ✅ `fastapi` - REST API
- ⚠️ **Order execution** - HITL approval required

### Guardrails de Segurança
- 🔒 Sandbox obrigatório para estratégias
- 🔒 API keys via env vars (NUNCA em código)
- 🔒 Position size limit: 5% do portfolio
- 🔒 Stop loss obrigatório: -3% por trade
- 🔒 Max daily loss: -5% do portfolio
- 🔒 HITL approval para TODAS as ordens (L1 autonomy)
- 🔒 Ledger imutável de decisões

### Resource Budget
- Tokens/interaction: 8000 max
- API cost/task: $0.05 max
- Timeout: 30 segundos
- Concurrent analysis: 3 max

---

## 🎯 INTENÇÃO

### Objetivo Primário
Criar a estrutura base completa do projeto seguindo BuildToValue v6.1, incluindo:

1. **Estrutura de Diretórios Completa**
2. **Arquivos de Configuração Base** (.env, docker-compose, requirements.txt)
3. **Agentes Fundamentais** (StrategyAgent, RiskAgent, ExecutionAgent)
4. **Sistema de Guardrails** (SecurityConfig, OrderValidator)
5. **Ledger de Auditoria** (append-only logging)
6. **Dashboard Básico** (Streamlit MVP)
7. **Testes Fundamentais** (unit + integration stubs)
8. **Documentação Inicial** (README, ADRs essenciais)

### Success Criteria
- [ ] Estrutura completa criada e validada
- [ ] Todos os arquivos de configuração funcionais
- [ ] Agentes base implementados com interfaces corretas
- [ ] Guardrails ativos e testados
- [ ] Paper trading mode funcional
- [ ] Testes básicos passando
- [ ] Documentação clara para evolução

### Monitoring Checkpoints
1. **Post-structure:** Validar diretórios e arquivos base
2. **Post-agents:** Testar instanciação dos agentes
3. **Post-guardrails:** Validar bloqueio de ordens perigosas
4. **Post-integration:** Smoke test do fluxo completo

---

## 📁 ESTRUTURA DE DIRETÓRIOS A CRIAR

```
crypto-ai-trader/
├── .buildtovalue/
│   ├── consensus/
│   │   ├── discovery-consensus.v6.json
│   │   └── decision-tree-pro.v6.json
│   ├── ledger/
│   │   ├── agent-decisions.jsonl
│   │   ├── trades.jsonl
│   │   └── overrides.log
│   ├── prompts/
│   │   └── registry.json
│   └── validations/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── strategy_agent.py
│   │   ├── risk_agent.py
│   │   └── execution_agent.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── ledger.py
│   │   └── exchange_client.py
│   ├── safety/
│   │   ├── __init__.py
│   │   ├── guardrails.py
│   │   ├── sandbox.py
│   │   └── security_config.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base_strategy.py
│   │   └── dca_optimized.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── market_data.py
│   │   └── indicators.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   └── squad_orchestrator.py
│   └── dashboard/
│       ├── __init__.py
│       └── app.py (Streamlit)
├── tests/
│   ├── unit/
│   │   ├── test_agents.py
│   │   ├── test_guardrails.py
│   │   └── test_strategies.py
│   ├── integration/
│   │   └── test_trading_flow.py
│   └── emergent/
│       └── test_agent_behavior.py
├── config/
│   ├── agents/
│   │   └── constitution.yaml
│   └── strategies/
│       └── risk_params.yaml
├── docs/
│   ├── ADR/
│   │   ├── 001-paper-trading-first.md
│   │   ├── 002-agent-architecture.md
│   │   └── 003-risk-management.md
│   └── tutorials/
│       └── getting_started.md
├── scripts/
│   ├── setup.sh
│   ├── validate.sh
│   └── backtest.sh
├── .env.example
├── .env
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 📝 ARQUIVOS BASE A CRIAR

### 1. requirements.txt
```txt
# Core
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0

# API & Web
fastapi==0.108.0
uvicorn[standard]==0.25.0
streamlit==1.29.0

# AI & Agents
langchain==0.1.0
langchain-google-genai==0.0.5
chromadb==0.4.22

# Trading & Market Data
ccxt==4.2.0
pandas==2.1.4
numpy==1.26.2
pandas-ta==0.3.14b

# Database & Storage
sqlalchemy==2.0.25
alembic==1.13.1

# Monitoring & Logging
prometheus-client==0.19.0
python-json-logger==2.0.7

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0

# Security
cryptography==41.0.7
```

### 2. .env.example
```bash
# Application
APP_ENV=development
LOG_LEVEL=INFO

# AI Models
GOOGLE_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_backup_key_here

# Exchange (Paper Trading)
EXCHANGE=binance
EXCHANGE_API_KEY=paper_trading_key
EXCHANGE_API_SECRET=paper_trading_secret
EXCHANGE_TESTNET=true

# Trading Parameters
INITIAL_CAPITAL=10000
MAX_POSITION_SIZE_PCT=5
STOP_LOSS_PCT=3
MAX_DAILY_LOSS_PCT=5
MAX_CONCURRENT_POSITIONS=3

# Autonomy
AUTONOMY_LEVEL=1
HITL_APPROVAL_REQUIRED=true

# Database
DATABASE_URL=sqlite:///./data/trading.db

# Vector Store
CHROMA_PERSIST_DIR=./data/chroma

# Monitoring
PROMETHEUS_PORT=9090
```

### 3. docker-compose.yml
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
      - "8501:8501"  # Streamlit
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    depends_on:
      - prometheus
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
    restart: unless-stopped

volumes:
  prometheus_data:
```

### 4. Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/logs

# Expose ports
EXPOSE 8000 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 🤖 CÓDIGO DOS AGENTES BASE

### src/agents/base_agent.py
```python
"""Base agent class for crypto trading system."""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all trading agents."""

    def __init__(self, agent_type: str) -> None:
        self.agent_type = agent_type
        self.agent_id = str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc)
        self.confidence_threshold = 0.6
        self.memory = None
        self.tools: list[str] = []

    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's primary responsibility."""
        pass

    def validate_input(self, task: Dict[str, Any]) -> bool:
        """Validate task input."""
        return bool(task)

    def log_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Log decision to memory and audit trail."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_type,
            "agent_id": self.agent_id,
            "decision": decision,
        }

        if self.memory:
            try:
                self.memory.remember_decision(self.agent_type, entry)
            except Exception as exc:
                logger.warning("Unable to persist agent memory", exc_info=exc)

        logger.info(f"{self.agent_type} recorded decision", extra={"decision": entry})
        return entry

    def attach_memory(self, memory: Any) -> None:
        """Attach memory backend."""
        self.memory = memory

    def validate_confidence(self, confidence: Optional[float]) -> bool:
        """Check if confidence meets threshold."""
        if confidence is None:
            return False
        return confidence >= self.confidence_threshold
```

### src/agents/strategy_agent.py
```python
"""Strategy agent for generating trading signals."""
from typing import Any, Dict
from src.agents.base_agent import BaseAgent
import logging

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """Generates trading signals using configured strategies."""

    def __init__(self) -> None:
        super().__init__("strategy")
        self.tools = ["market_data", "technical_indicators", "pattern_recognition"]
        self.active_strategies = []

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market and generate trading signals."""
        if not self.validate_input(task):
            raise ValueError("Invalid strategy task")

        symbol = task.get("symbol")
        timeframe = task.get("timeframe", "1h")

        # Chain-of-Thought reasoning for signal generation
        analysis = await self._analyze_market(symbol, timeframe)
        signal = await self._generate_signal(analysis)
        confidence = self._calculate_confidence(analysis, signal)

        decision = {
            "task": task,
            "analysis": analysis,
            "signal": signal,
            "confidence": confidence,
            "reasoning": self._explain_reasoning(analysis, signal)
        }

        self.log_decision(decision)

        return {
            "success": True,
            "agent": self.agent_type,
            "signal": signal,
            "confidence": confidence,
            "analysis": analysis
        }

    async def _analyze_market(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Perform market analysis (CoT step 1)."""
        # TODO: Implement with actual market data
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trend": "bullish",
            "momentum": 0.65,
            "volatility": "low"
        }

    async def _generate_signal(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate trading signal (CoT step 2)."""
        # TODO: Implement strategy logic
        return {
            "action": "BUY",
            "entry_price": 100.0,
            "stop_loss": 97.0,
            "take_profit": 105.0,
            "position_size_pct": 3.0
        }

    def _calculate_confidence(self, analysis: Dict[str, Any], signal: Dict[str, Any]) -> float:
        """Calculate confidence score (CoT step 3)."""
        # TODO: Implement confidence calculation
        return 0.75

    def _explain_reasoning(self, analysis: Dict[str, Any], signal: Dict[str, Any]) -> str:
        """Explain the reasoning behind the signal."""
        return f"Bullish trend detected with momentum {analysis['momentum']}, suggesting {signal['action']}"
```

### src/agents/risk_agent.py
```python
"""Risk management agent."""
from typing import Any, Dict
from src.agents.base_agent import BaseAgent
from src.safety.guardrails import GuardrailSystem
import logging

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """Validates trades against risk management rules."""

    def __init__(self) -> None:
        super().__init__("risk")
        self.tools = ["portfolio_analyzer", "risk_calculator"]
        self.guardrails = GuardrailSystem()
        self.max_position_size_pct = 5.0
        self.stop_loss_pct = 3.0
        self.max_daily_loss_pct = 5.0

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trade proposal against risk rules."""
        if not self.validate_input(task):
            raise ValueError("Invalid risk validation task")

        signal = task.get("signal", {})
        portfolio = task.get("portfolio", {})

        # Reflection pattern: validate → reflect → refine
        initial_validation = await self._validate_signal(signal, portfolio)
        reflection = await self._reflect_on_validation(initial_validation)
        final_validation = self._refine_validation(initial_validation, reflection)

        decision = {
            "task": task,
            "initial_validation": initial_validation,
            "reflection": reflection,
            "final_validation": final_validation,
            "confidence": final_validation.get("confidence", 0.0)
        }

        self.log_decision(decision)

        return {
            "success": True,
            "agent": self.agent_type,
            "approved": final_validation["approved"],
            "validation": final_validation,
            "confidence": final_validation.get("confidence", 0.0)
        }

    async def _validate_signal(self, signal: Dict[str, Any], portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Initial validation."""
        issues = []
        warnings = []

        # Check position size
        position_size = signal.get("position_size_pct", 0)
        if position_size > self.max_position_size_pct:
            issues.append(f"Position size {position_size}% exceeds limit {self.max_position_size_pct}%")

        # Check stop loss
        entry = signal.get("entry_price", 0)
        stop = signal.get("stop_loss", 0)
        if entry > 0:
            stop_loss_pct = abs((stop - entry) / entry * 100)
            if stop_loss_pct > self.stop_loss_pct:
                warnings.append(f"Stop loss {stop_loss_pct:.2f}% is wider than recommended {self.stop_loss_pct}%")

        approved = len(issues) == 0
        confidence = 0.9 if approved else 0.3

        return {
            "approved": approved,
            "issues": issues,
            "warnings": warnings,
            "confidence": confidence
        }

    async def _reflect_on_validation(self, validation: Dict[str, Any]) -> Dict[str, Any]:
        """Reflect on validation to catch edge cases."""
        reflection = {
            "missed_anything": False,
            "too_strict": False,
            "suggestions": []
        }

        if validation["approved"] and len(validation["warnings"]) > 2:
            reflection["missed_anything"] = True
            reflection["suggestions"].append("Review warnings for hidden risks")

        return reflection

    def _refine_validation(self, validation: Dict[str, Any], reflection: Dict[str, Any]) -> Dict[str, Any]:
        """Refine validation based on reflection."""
        final = dict(validation)

        if reflection["missed_anything"]:
            final["confidence"] = min(final["confidence"], 0.75)
            final["requires_review"] = True

        final["refined"] = True
        final["reflection_applied"] = reflection
        return final
```

### src/agents/execution_agent.py
```python
"""Execution agent for order management."""
from typing import Any, Dict
from src.agents.base_agent import BaseAgent
from src.core.exchange_client import ExchangeClient
import logging
import uuid

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """Executes validated trades on exchange."""

    def __init__(self, exchange_client: ExchangeClient) -> None:
        super().__init__("execution")
        self.tools = ["place_order", "cancel_order", "get_order_status"]
        self.exchange = exchange_client
        self.paper_trading = True  # Always true for MVP

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validated order."""
        if not self.validate_input(task):
            raise ValueError("Invalid execution task")

        signal = task.get("signal", {})
        human_approved = task.get("human_approved", False)

        if not human_approved:
            return {
                "success": False,
                "agent": self.agent_type,
                "error": "Human approval required (HITL)",
                "confidence": 0.0
            }

        # ReAct loop for execution
        result = await self._react_execution(signal)

        decision = {
            "task": task,
            "result": result,
            "confidence": result.get("confidence", 0.0)
        }

        self.log_decision(decision)

        return {
            "success": result["success"],
            "agent": self.agent_type,
            "order_id": result.get("order_id"),
            "confidence": result.get("confidence", 0.0)
        }

    async def _react_execution(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """ReAct pattern for order execution."""
        # Thought
        thought = f"Need to execute {signal['action']} order for {signal.get('symbol')}"
        logger.info(f"[THOUGHT] {thought}")

        # Action
        if self.paper_trading:
            action = "simulate_order"
        else:
            action = "place_real_order"

        logger.info(f"[ACTION] {action}")

        # Observation
        if action == "simulate_order":
            observation = {
                "success": True,
                "order_id": "PAPER_" + str(uuid.uuid4())[:8],
                "status": "filled",
                "message": "Paper trade simulated successfully"
            }
        else:
            # TODO: Implement real order placement
            observation = {"success": False, "error": "Real trading not implemented"}

        logger.info(f"[OBSERVATION] {observation}")

        # Answer
        confidence = 1.0 if observation["success"] else 0.0
        return {**observation, "confidence": confidence}
```

---

## 🔒 SISTEMA DE GUARDRAILS

### src/safety/security_config.py
```python
"""Security configuration and constants."""
from dataclasses import dataclass
from typing import List, Tuple, Dict
import re


@dataclass
class SecurityConfig:
    """Security configuration for trading operations."""

    MAX_POSITION_SIZE_PCT: float = 5.0
    MAX_STOP_LOSS_PCT: float = 3.0
    MAX_DAILY_LOSS_PCT: float = 5.0
    MAX_CONCURRENT_POSITIONS: int = 3
    MAX_EXECUTION_TIME_SECONDS: int = 30

    FORBIDDEN_PATTERNS: List[str] = None

    def __post_init__(self):
        if self.FORBIDDEN_PATTERNS is None:
            self.FORBIDDEN_PATTERNS = [
                r"leverage.*10x",
                r"margin.*call",
                r"liquidation",
                r"all.*in",
                r"100%.*position"
            ]

    ALLOWED_EXCHANGES = {"binance", "coinbase", "kraken"}
    HIGH_RISK_ACTIONS = {"market_order", "stop_market", "leverage_trade"}

    @classmethod
    def validate_order(cls, order: Dict) -> Tuple[bool, str]:
        """Validate order against security rules."""
        # Check position size
        position_size = order.get("position_size_pct", 0)
        if position_size > cls.MAX_POSITION_SIZE_PCT:
            return False, f"Position size {position_size}% exceeds limit {cls.MAX_POSITION_SIZE_PCT}%"

        # Check for forbidden patterns in notes
        notes = str(order.get("notes", ""))
        for pattern in cls().FORBIDDEN_PATTERNS:
            if re.search(pattern, notes, re.IGNORECASE):
                return False, f"Forbidden pattern detected: {pattern}"

        # Check exchange
        exchange = order.get("exchange", "").lower()
        if exchange not in cls.ALLOWED_EXCHANGES:
            return False, f"Exchange {exchange} not in allowed list"

        return True, "OK"
```

### src/safety/guardrails.py
```python
"""Guardrail system for order validation."""
from typing import List, Tuple, Dict, Callable
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

Guardrail = Callable[[Dict], Tuple[bool, str]]


@dataclass
class GuardrailSystem:
    """Collection of guardrails for trade validation."""

    rules: List[Guardrail] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.rules:
            self.rules = [
                self.check_position_size,
                self.check_stop_loss,
                self.check_risk_reward,
                self.check_market_conditions
            ]

    def validate_order(self, order: Dict) -> Tuple[bool, List[str]]:
        """Validate order against all guardrails."""
        violations: List[str] = []

        for rule in self.rules:
            passed, message = rule(order)
            if not passed and message:
                violations.append(message)
                logger.warning(f"Guardrail violation: {message}")

        return len(violations) == 0, violations

    def check_position_size(self, order: Dict) -> Tuple[bool, str]:
        """Validate position size."""
        max_size = 5.0
        position_size = order.get("position_size_pct", 0)

        if position_size > max_size:
            return False, f"Position size {position_size}% exceeds maximum {max_size}%"

        return True, ""

    def check_stop_loss(self, order: Dict) -> Tuple[bool, str]:
        """Validate stop loss is present."""
        if "stop_loss" not in order or order["stop_loss"] is None:
            return False, "Stop loss is mandatory"

        entry = order.get("entry_price", 0)
        stop = order["stop_loss"]

        if entry > 0:
            action = order.get("action", "").upper()
            if action == "BUY" and stop >= entry:
                return False, "Stop loss must be below entry for BUY orders"
            elif action == "SELL" and stop <= entry:
                return False, "Stop loss must be above entry for SELL orders"

        return True, ""

    def check_risk_reward(self, order: Dict) -> Tuple[bool, str]:
        """Validate risk-reward ratio."""
        entry = order.get("entry_price", 0)
        stop = order.get("stop_loss", 0)
        target = order.get("take_profit", 0)

        if entry > 0 and stop > 0 and target > 0:
            risk = abs(entry - stop)
            reward = abs(target - entry)

            if risk > 0:
                rr_ratio = reward / risk
                if rr_ratio < 1.5:
                    return False, f"Risk-reward ratio {rr_ratio:.2f} is below minimum 1.5"

        return True, ""

    def check_market_conditions(self, order: Dict) -> Tuple[bool, str]:
        """Check if market conditions are suitable."""
        # TODO: Implement market condition checks
        # For now, always pass
        return True, ""
```

---

## 📊 LEDGER DE AUDITORIA

### src/core/ledger.py
```python
"""Immutable audit ledger for all trading decisions."""
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class TradingLedger:
    """Append-only ledger for audit trail."""

    def __init__(self, ledger_path: Path = None):
        self.ledger_path = ledger_path or Path(".buildtovalue/ledger/trades.jsonl")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def log_decision(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log a trading decision to the ledger."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data
        }

        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"Ledger entry: {event_type}", extra=entry)

    def log_signal(self, agent: str, signal: Dict[str, Any]) -> None:
        """Log a trading signal."""
        self.log_decision("signal_generated", {
            "agent": agent,
            "signal": signal
        })

    def log_validation(self, agent: str, validation: Dict[str, Any]) -> None:
        """Log a risk validation."""
        self.log_decision("risk_validation", {
            "agent": agent,
            "validation": validation
        })

    def log_execution(self, agent: str, execution: Dict[str, Any]) -> None:
        """Log an order execution."""
        self.log_decision("order_executed", {
            "agent": agent,
            "execution": execution
        })

    def log_hitl_approval(self, approved: bool, order: Dict[str, Any], user: str = "default") -> None:
        """Log human-in-the-loop approval decision."""
        self.log_decision("hitl_approval", {
            "approved": approved,
            "order": order,
            "user": user
        })

    def get_recent_trades(self, limit: int = 100) -> list:
        """Retrieve recent trades from ledger."""
        if not self.ledger_path.exists():
            return []

        trades = []
        with self.ledger_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    trades.append(json.loads(line))

        return trades[-limit:]
```

---

## 🎯 ORQUESTRAÇÃO DA SQUAD

### src/orchestration/squad_orchestrator.py
```python
"""Orchestrator for multi-agent trading operations."""
from typing import Dict, Any
from src.agents.strategy_agent import StrategyAgent
from src.agents.risk_agent import RiskAgent
from src.agents.execution_agent import ExecutionAgent
from src.core.ledger import TradingLedger
import logging

logger = logging.getLogger(__name__)


class SquadOrchestrator:
    """Coordinates strategy, risk, and execution agents."""

    def __init__(self, exchange_client):
        self.strategy_agent = StrategyAgent()
        self.risk_agent = RiskAgent()
        self.execution_agent = ExecutionAgent(exchange_client)
        self.ledger = TradingLedger()

    async def analyze_and_trade(self, symbol: str, timeframe: str = "1h") -> Dict[str, Any]:
        """Full trading pipeline with agent collaboration."""
        logger.info(f"Starting analysis for {symbol} ({timeframe})")

        # Step 1: Strategy Agent generates signal
        strategy_result = await self.strategy_agent.execute({
            "symbol": symbol,
            "timeframe": timeframe
        })

        self.ledger.log_signal(
            agent="strategy",
            signal=strategy_result["signal"]
        )

        if strategy_result["confidence"] < 0.6:
            logger.info("Signal confidence too low, skipping")
            return {
                "success": False,
                "reason": "Low confidence signal",
                "confidence": strategy_result["confidence"]
            }

        # Step 2: Risk Agent validates signal
        risk_result = await self.risk_agent.execute({
            "signal": strategy_result["signal"],
            "portfolio": {}  # TODO: Get actual portfolio
        })

        self.ledger.log_validation(
            agent="risk",
            validation=risk_result["validation"]
        )

        if not risk_result["approved"]:
            logger.warning("Signal rejected by Risk Agent")
            return {
                "success": False,
                "reason": "Risk validation failed",
                "issues": risk_result["validation"]["issues"]
            }

        # Step 3: HITL Approval (always required in L1 autonomy)
        logger.info("⏸️  HITL approval required")
        # In production, this would trigger UI notification
        # For now, we simulate approval
        human_approved = True  # TODO: Implement real HITL

        self.ledger.log_hitl_approval(
            approved=human_approved,
            order=strategy_result["signal"]
        )

        if not human_approved:
            return {
                "success": False,
                "reason": "Human rejected the trade"
            }

        # Step 4: Execution Agent places order
        execution_result = await self.execution_agent.execute({
            "signal": strategy_result["signal"],
            "human_approved": human_approved
        })

        self.ledger.log_execution(
            agent="execution",
            execution=execution_result
        )

        return {
            "success": execution_result["success"],
            "order_id": execution_result.get("order_id"),
            "signal": strategy_result["signal"],
            "confidence": strategy_result["confidence"]
        }
```

---

## 📋 FORMATO DE ENTREGA

### Estrutura de Commits
```
1. feat: initialize project structure with BuildToValue v6.1
2. feat: add base agent classes and interfaces
3. feat: implement strategy agent with CoT reasoning
4. feat: implement risk agent with reflection pattern
5. feat: implement execution agent with ReAct loop
6. feat: add guardrail system and security config
7. feat: add trading ledger for audit trail
8. feat: add squad orchestrator for agent coordination
9. docs: add initial ADRs and README
10. test: add unit tests for agents and guardrails
```

### Validation Commands
```bash
# Após implementação, executar:
python -m pytest tests/ -v
python -m black src/ tests/
python -m flake8 src/ tests/
python -m mypy src/
```

### Success Indicators
- ✅ All tests passing
- ✅ Code coverage > 70%
- ✅ No security warnings
- ✅ Guardrails blocking invalid orders
- ✅ Ledger recording all decisions
- ✅ Paper trading mode functional

---

## 🚨 ALERTAS E ESCALATION

**Escalar para PE se:**
- Conflito de decisões entre agentes (consensus < 0.5)
- Violações de guardrails repetidas
- Comportamento emergente não previsto
- Timeout em decisões críticas
- Custos de API > budget

---

## ✅ CHECKLIST DE VALIDAÇÃO

- [ ] Estrutura de diretórios completa
- [ ] Arquivos de configuração (.env, docker-compose, requirements.txt)
- [ ] Agentes base (Strategy, Risk, Execution) implementados
- [ ] Guardrails ativos e validados
- [ ] Ledger de auditoria funcional
- [ ] Orquestrador de squad operacional
- [ ] Testes unitários básicos
- [ ] README e documentação inicial
- [ ] Paper trading mode habilitado
- [ ] HITL approval workflow definido

---

**🎯 OBJETIVO FINAL:** Sistema base funcional com agentes colaborando de forma segura em paper trading mode, pronto para evoluir com novas capacidades.

**⏰ PRAZO:** 3-5 dias para implementação inicial  
**💰 CUSTO ESTIMADO:** $0 (sem custos de infra/API até deployment)  
**🔒 SEGURANÇA:** Prioridade máxima em todas as decisões
