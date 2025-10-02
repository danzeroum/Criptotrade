"""Centralised security configuration for tool executions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class SecurityConfig:
    MAX_EXECUTION_TIME_SECONDS: int = 30
    MAX_MEMORY_PER_TOOL_MB: int = 512
    MAX_CONCURRENT_TOOLS: int = 5

    FORBIDDEN_PATTERNS = [
        r"rm\s+-rf\s+/",
        r":\(\)\{ :\|:& \};:",
        r"dd\s+if=/dev/zero",
        r"DROP\s+DATABASE",
        r"<script",
        r"eval\(",
        r"__import__",
        r"os\.system",
        r"subprocess\.",
        r"socket\."
    ]

    ALLOWED_DOMAINS = {"api.BuildToValue.com", "localhost", "127.0.0.1"}
    HIGH_RISK_TOOLS = {"database_write", "send_email", "make_payment", "delete_resource", "modify_production_config"}

    @classmethod
    def validate_tool_call(cls, tool_name: str, params: Dict[str, object]) -> Tuple[bool, str]:
        if tool_name in cls.HIGH_RISK_TOOLS:
            return False, f"Tool {tool_name} requires human approval"
        payload = str(params)
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, payload, re.IGNORECASE):
                return False, f"Forbidden pattern detected: {pattern}"
        return True, "OK"
