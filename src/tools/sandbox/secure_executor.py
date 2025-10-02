"""Security sandbox for executing tools with strict validation."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.safety.security_config import SecurityConfig
from .docker_sandbox import DockerSandbox

logger = logging.getLogger(__name__)


class SecurityError(RuntimeError):
    """Raised when a tool invocation violates security guardrails."""


@dataclass
class SecureToolSandbox:
    """Provides validation and optional containerised tool execution."""

    docker_sandbox: Optional[DockerSandbox] = None
    execution_timeout: int = 30
    memory_limit_mb: int = 512
    cpu_quota: float = 0.5

    def execute_tool_sandboxed(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the given tool inside an isolated environment when possible."""

        self._validate_security(tool_name, params)

        if self.docker_sandbox is None:
            logger.warning("Docker sandbox unavailable; returning simulated response")
            return {
                "tool": tool_name,
                "params": params,
                "sandboxed": False,
                "message": "Docker indisponível, execução simulada",
            }

        command = ["python", "-m", tool_name]
        output = self.docker_sandbox.run(
            command,
            environment={"PARAMS": json.dumps(params)},
            timeout=self.execution_timeout,
        )
        return {"tool": tool_name, "output": output, "sandboxed": True}

    def _validate_security(self, tool_name: str, params: Dict[str, Any]) -> None:
        is_safe, reason = SecurityConfig.validate_tool_call(tool_name, params)
        if not is_safe:
            raise SecurityError(f"Tool execution blocked: {reason}")
        if not self._validate_params_safety(params):
            raise ValueError(f"Dangerous parameters detected for {tool_name}")

    def _validate_params_safety(self, params: Dict[str, Any]) -> bool:
        param_str = json.dumps(params, ensure_ascii=False)
        for pattern in SecurityConfig.FORBIDDEN_PATTERNS:
            if re.search(pattern, param_str, re.IGNORECASE):
                logger.error("Forbidden pattern detected during sandbox validation", extra={"pattern": pattern})
                return False
        return True
