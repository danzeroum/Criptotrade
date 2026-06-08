"""Trading strategy implementations."""
from .base_strategy import BaseStrategy
from .dca_optimized import DCAOptimizedStrategy

# Lazy imports to avoid circular dependency issues at module load time.
# GridTradingStrategy and MeanReversionStrategy are added as they are implemented.
try:
    from .grid_trading import GridTradingStrategy
except ImportError:  # not yet implemented
    GridTradingStrategy = None  # type: ignore[assignment,misc]

try:
    from .mean_reversion import MeanReversionStrategy
except ImportError:  # not yet implemented
    MeanReversionStrategy = None  # type: ignore[assignment,misc]

STRATEGY_REGISTRY: dict = {
    "dca": DCAOptimizedStrategy,
}
if GridTradingStrategy is not None:
    STRATEGY_REGISTRY["grid"] = GridTradingStrategy
if MeanReversionStrategy is not None:
    STRATEGY_REGISTRY["mean_reversion"] = MeanReversionStrategy

__all__ = [
    "BaseStrategy",
    "DCAOptimizedStrategy",
    "STRATEGY_REGISTRY",
]
