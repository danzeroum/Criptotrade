"""Security configuration and constants."""
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
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
