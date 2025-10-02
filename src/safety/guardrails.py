"""Guardrail system to validate agent outputs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple


Guardrail = Callable[[str, Dict[str, object]], Tuple[bool, str]]


@dataclass
class GuardrailSystem:
    """Collection of guardrail rules that can be evaluated sequentially."""

    rules: List[Guardrail] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.rules:
            self.rules = [
                self.check_no_pii,
                self.check_no_harmful_code,
                self.check_business_logic_consistency,
                self.check_performance_bounds,
            ]

    def validate_output(self, output: str, context: Dict[str, object]) -> Tuple[bool, List[str]]:
        """Validate the output against configured guardrails."""

        violations: List[str] = []
        for rule in self.rules:
            passed, message = rule(output, context)
            if not passed and message:
                violations.append(message)
        return len(violations) == 0, violations

    def check_no_pii(self, output: str, context: Dict[str, object]) -> Tuple[bool, str]:
        patterns = [r"\b\d{3}-\d{3}-\d{3}\b", r"\b\d{11}\b"]
        for pattern in patterns:
            if re.search(pattern, output):
                return False, "Possível PII detectada"
        return True, ""

    def check_no_harmful_code(self, output: str, context: Dict[str, object]) -> Tuple[bool, str]:
        dangerous_patterns = [r"rm\s+-rf\s+/", r"DROP\s+DATABASE", r"eval\(", r"__import__\("]
        for pattern in dangerous_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return False, f"Código potencialmente perigoso detectado: {pattern}"
        return True, ""

    def check_business_logic_consistency(self, output: str, context: Dict[str, object]) -> Tuple[bool, str]:
        required_terms = context.get("required_terms", [])
        for term in required_terms:
            if term not in output:
                return False, f"Termo obrigatório ausente: {term}"
        return True, ""

    def check_performance_bounds(self, output: str, context: Dict[str, object]) -> Tuple[bool, str]:
        limit = context.get("latency_budget_ms")
        if isinstance(limit, (int, float)):
            try:
                latency = float(context.get("estimated_latency_ms", 0))
            except (TypeError, ValueError):
                latency = 0.0
            if latency > limit:
                return False, "Latência estimada acima do limite"
        return True, ""
