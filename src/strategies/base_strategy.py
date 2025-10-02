"""Base strategy interface for trading strategies."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    @abstractmethod
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform analysis and return a strategy decision."""

    def get_parameters(self) -> Dict[str, Any]:
        """Return strategy configuration parameters."""
        return {}
