"""High-level orchestrator connecting core agent components."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.core.safe_agent_base import AgentExecution, SafeAgentBase
from src.evaluation.continuous_eval import ContinuousEvaluator
from src.protocols.mcp_server import MCPServer
from src.tools.rag_tool import RAGTool


class _NoopSpan:
    def __enter__(self) -> None:  # pragma: no cover - minimal span implementation
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:  # pragma: no cover - minimal span implementation
        return False


class NullObserver:
    """Fallback observability helper when no tracer is available."""

    def start_span(self, name: str) -> _NoopSpan:  # pragma: no cover - minimal span implementation
        return _NoopSpan()


class AgentOrchestrator:
    """Integra agente base, RAG, MCP e avaliação contínua."""

    def __init__(self, vector_db_url: str, metrics_config: Optional[Dict[str, Any]] = None) -> None:
        self.base_agent = SafeAgentBase()
        self.base_agent.add_capability("memory")
        self.base_agent.add_capability("planning")

        self.evaluator = ContinuousEvaluator(metrics_config or {})
        self.rag_tool = RAGTool(vector_db_url)
        self.observer = NullObserver()
        self.mcp_server = MCPServer(self.base_agent)

    def execute_with_monitoring(self, task: str) -> Tuple[AgentExecution, Dict[str, Any]]:
        """Executa uma tarefa integrando recuperação de contexto e avaliação."""

        rag_context = self._prepare_context(self.rag_tool.retrieve(task))

        with self.observer.start_span("task_execution"):
            execution = self.base_agent.execute(task, rag_context)

        evaluation = self.evaluator.evaluate_trajectory(execution)
        return execution, evaluation

    def _prepare_context(self, retrieval_result: Any) -> Optional[str]:
        if isinstance(retrieval_result, list):
            if not retrieval_result:
                return None
            return "\n".join(str(item) for item in retrieval_result)
        if isinstance(retrieval_result, str):
            return retrieval_result
        return None

    def publish_agent_card(self) -> Dict[str, Any]:
        """Exponibiliza metadados do agente via MCP."""

        return self.mcp_server.publish_agent_card()


__all__ = ["AgentOrchestrator"]
