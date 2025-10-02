#!/usr/bin/env bash
set -euo pipefail

echo "🤖 Validando BuildToValue v6.1 - Agentes Completos"

echo "🔒 Testando Sandbox..."
python - <<'PY'
from src.tools.sandbox.secure_executor import SecureToolSandbox
sandbox = SecureToolSandbox()
try:
    sandbox.validate_invocation("rm", {"-rf": "/"})
except ValueError:
    print("✅ Sandbox bloqueou comando perigoso")
else:
    raise SystemExit("❌ Sandbox permitiu comando perigoso")
PY

echo "🤝 Testando Consenso..."
python - <<'PY'
from src.consensus.weighted_voting import WeightedConsensusEngine
engine = WeightedConsensusEngine()
proposals = {
    "architect": {"confidence": 0.8, "choice": "A"},
    "developer": {"confidence": 0.6, "choice": "B"},
    "auditor": {"confidence": 0.9, "choice": "A"},
}
print(engine.reach_consensus(proposals, "architecture"))
PY

echo "🔄 Testando Replanejamento..."
python - <<'PY'
import asyncio
from src.planning.adaptive_replanner import AdaptivePlanner

planner = AdaptivePlanner()
async def main():
    plan = {"goal": "demo", "steps": []}
    result = await planner.execute_with_replanning(plan)
    print(result)

asyncio.run(main())
PY

echo "🧠 Testando Memória Inteligente..."
python - <<'PY'
from src.memory.agent_memory import AgentMemorySystem
memory = AgentMemorySystem()
memory.remember_decision("test", {"summary": "demo", "confidence": 0.5})
print(memory.recall_similar("demo"))
PY

echo "✅ Todos os testes básicos executados"
