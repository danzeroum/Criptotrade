"""Minimal MCP (Model Context Protocol) server exposure for agent capabilities."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List


class MCPServer:
    """Expõe capacidades do agente via MCP."""

    def __init__(self, agent: Any) -> None:
        self.agent = agent
        self.capabilities = self.discover_capabilities()

    def discover_capabilities(self) -> List[str]:
        """Descobre capacidades do agente a partir da interface pública."""

        if hasattr(self.agent, "list_capabilities"):
            capabilities = self.agent.list_capabilities()
            return list(capabilities)
        if hasattr(self.agent, "capabilities"):
            return list(self.agent.capabilities)
        return []

    def get_endpoint(self) -> str:
        """Retorna o endpoint MCP publicado pelo agente."""

        return getattr(self.agent, "endpoint", "mcp://localhost")

    def publish_agent_card(self) -> Dict[str, Any]:
        """Publica metadados do agente conforme o protocolo MCP."""

        agent_name = getattr(self.agent, "name", "anonymous-agent")
        self.capabilities = self.discover_capabilities()
        return {
            "name": agent_name,
            "skills": self.capabilities,
            "endpoint": self.get_endpoint(),
        }

    def handle_request(self, request: Any) -> Any:
        """Processa requisições MCP."""

        request_type = getattr(request, "type", None)
        if request_type is None and isinstance(request, dict):
            request_type = request.get("type")

        if request_type == "discover":
            return self.publish_agent_card()

        if request_type == "execute":
            payload = getattr(request, "payload", None)
            if payload is None and isinstance(request, dict):
                payload = request.get("payload")

            if not hasattr(self.agent, "execute"):
                raise AttributeError("Agent does not expose an execute method.")

            if isinstance(payload, dict):
                result = self.agent.execute(**payload)
            else:
                result = self.agent.execute(payload) if payload is not None else self.agent.execute("")

            if is_dataclass(result):
                return asdict(result)
            if hasattr(result, "to_dict"):
                return result.to_dict()
            return result

        raise ValueError(f"Unsupported MCP request type: {request_type}")
