"""Security configuration and constants."""
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Tuple
import json
import re


@dataclass
class SecurityConfig:
    """Security configuration for trading operations."""

    MAX_POSITION_SIZE_PCT: float = 5.0
    MAX_STOP_LOSS_PCT: float = 3.0
    MAX_DAILY_LOSS_PCT: float = 5.0
    MAX_CONCURRENT_POSITIONS: int = 3
    MAX_EXECUTION_TIME_SECONDS: int = 30

    FORBIDDEN_PATTERNS: List[str] | None = None
    FORBIDDEN_TOOL_NAMES: ClassVar[Tuple[str, ...]] = (
        "rm",
        "delete_resource",
        "format_disk",
        "drop_database",
    )
    SENSITIVE_PARAM_PATTERNS: ClassVar[Tuple[str, ...]] = (
        r"rm\s+-rf",
        r"drop\s+table",
        r"delete\s+from",
        r"format\s+",
    )

    def __post_init__(self) -> None:
        if self.FORBIDDEN_PATTERNS is None:
            self.FORBIDDEN_PATTERNS = [
                r"leverage.*10x",
                r"margin.*call",
                r"liquidation",
                r"all.*in",
                r"100%.*position",
            ]

    ALLOWED_EXCHANGES = {"binance", "coinbase", "kraken"}
    HIGH_RISK_ACTIONS = {"market_order", "stop_market", "leverage_trade"}

    @classmethod
    def validate_order(cls, order: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate order against security rules."""
        position_size = order.get("position_size_pct", 0)
        if position_size > cls.MAX_POSITION_SIZE_PCT:
            return False, f"Position size {position_size}% exceeds limit {cls.MAX_POSITION_SIZE_PCT}%"

        notes = str(order.get("notes", ""))
        for pattern in cls().FORBIDDEN_PATTERNS or []:
            if re.search(pattern, notes, re.IGNORECASE):
                return False, f"Forbidden pattern detected: {pattern}"

        exchange = order.get("exchange", "").lower()
        if exchange and exchange not in cls.ALLOWED_EXCHANGES:
            return False, f"Exchange {exchange} not in allowed list"

        return True, "OK"

    @classmethod
    def validate_tool_call(cls, tool_name: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate whether a tool invocation is allowed within the sandbox."""

        normalized = tool_name.lower()
        if normalized in cls.FORBIDDEN_TOOL_NAMES:
            return False, f"Tool {tool_name} is blocked by security policy"

        param_blob = json.dumps(params, ensure_ascii=False)
        combined_patterns = list(cls().FORBIDDEN_PATTERNS or []) + list(cls.SENSITIVE_PARAM_PATTERNS)
        for pattern in combined_patterns:
            if re.search(pattern, param_blob, re.IGNORECASE):
                return False, f"Parameters match forbidden pattern: {pattern}"

        return True, "OK"
