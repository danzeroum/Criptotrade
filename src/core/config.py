"""Configuration management for the crypto trading platform."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # AI Models
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")

    # Exchange Configuration
    exchange: str = Field(default="binance", alias="EXCHANGE")
    exchange_api_key: Optional[str] = Field(default=None, alias="EXCHANGE_API_KEY")
    exchange_api_secret: Optional[str] = Field(default=None, alias="EXCHANGE_API_SECRET")
    exchange_testnet: bool = Field(default=True, alias="EXCHANGE_TESTNET")

    # Trading Parameters
    initial_capital: float = Field(default=10000.0, alias="INITIAL_CAPITAL")
    max_position_size_pct: float = Field(default=5.0, alias="MAX_POSITION_SIZE_PCT")
    stop_loss_pct: float = Field(default=3.0, alias="STOP_LOSS_PCT")
    max_daily_loss_pct: float = Field(default=5.0, alias="MAX_DAILY_LOSS_PCT")
    max_concurrent_positions: int = Field(default=3, alias="MAX_CONCURRENT_POSITIONS")

    # Autonomy Settings
    autonomy_level: int = Field(default=1, alias="AUTONOMY_LEVEL")  # 1-5
    hitl_approval_required: bool = Field(default=True, alias="HITL_APPROVAL_REQUIRED")

    # Database
    database_url: str = Field(
        default="sqlite:///./data/trading.db",
        alias="DATABASE_URL"
    )

    # Vector Store
    chroma_persist_dir: str = Field(
        default="./data/chroma",
        alias="CHROMA_PERSIST_DIR"
    )

    # Monitoring
    prometheus_port: int = Field(default=9090, alias="PROMETHEUS_PORT")

    # Resource Limits
    max_tokens_per_interaction: int = Field(
        default=8000,
        alias="MAX_TOKENS_PER_INTERACTION"
    )
    max_api_cost_per_task: float = Field(
        default=0.05,
        alias="MAX_API_COST_PER_TASK"
    )
    timeout_seconds: int = Field(default=30, alias="TIMEOUT_SECONDS")
    max_concurrent_analysis: int = Field(
        default=3,
        alias="MAX_CONCURRENT_ANALYSIS"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
LEDGER_DIR = PROJECT_ROOT / ".buildtovalue" / "ledger"
CONFIG_DIR = PROJECT_ROOT / "config"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
LEDGER_DIR.mkdir(parents=True, exist_ok=True)


def configure_logging() -> None:
    """Configure application-wide logging."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(log_format))

        file_handler = logging.FileHandler(LOGS_DIR / "trading.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))

        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

    # Reduce noise from external libraries
    logging.getLogger("ccxt").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger.info("Logging configured", extra={"level": settings.log_level})


def validate_configuration() -> None:
    """Validate critical configuration settings."""
    errors = []
    warnings = []

    # Check API keys
    if not settings.google_api_key and not settings.openai_api_key:
        errors.append("No AI API keys configured (GOOGLE_API_KEY or OPENAI_API_KEY)")

    # Check exchange configuration
    if not settings.exchange_testnet:
        warnings.append(
            "EXCHANGE_TESTNET=false detected. Make sure you intend to use LIVE trading!"
        )

    # Check risk parameters
    if settings.max_position_size_pct > 10.0:
        warnings.append(
            f"MAX_POSITION_SIZE_PCT={settings.max_position_size_pct}% is high. Recommended: <=5%"
        )

    if settings.stop_loss_pct > 5.0:
        warnings.append(
            f"STOP_LOSS_PCT={settings.stop_loss_pct}% is wide. Recommended: <=3%"
        )

    # Check autonomy level
    if settings.autonomy_level > 2 and settings.app_env == "production":
        warnings.append(
            f"AUTONOMY_LEVEL={settings.autonomy_level} in production. Consider L1 or L2 for safety."
        )

    if not settings.hitl_approval_required and settings.autonomy_level == 1:
        errors.append(
            "HITL_APPROVAL_REQUIRED=false but AUTONOMY_LEVEL=1 (inconsistent configuration)"
        )

    if errors:
        logger.error("Configuration validation failed!", extra={"errors": errors})
        raise ValueError("Invalid configuration. See errors above.")

    if warnings:
        for warning in warnings:
            logger.warning(warning)
    else:
        logger.info("Configuration validated successfully")


def get_risk_params() -> Dict[str, float]:
    """Get risk management parameters from settings."""
    return {
        "max_position_size_pct": settings.max_position_size_pct,
        "stop_loss_pct": settings.stop_loss_pct,
        "max_daily_loss_pct": settings.max_daily_loss_pct,
        "max_concurrent_positions": settings.max_concurrent_positions,
    }


def get_resource_limits() -> Dict[str, float]:
    """Get resource limit parameters."""
    return {
        "max_tokens_per_interaction": settings.max_tokens_per_interaction,
        "max_api_cost_per_task": settings.max_api_cost_per_task,
        "timeout_seconds": settings.timeout_seconds,
        "max_concurrent_analysis": settings.max_concurrent_analysis,
    }


def is_paper_trading() -> bool:
    """Check if system is in paper trading mode."""
    if settings.app_env == "development":
        return True
    return settings.exchange_testnet


def get_autonomy_config() -> Dict[str, Any]:
    """Get autonomy level configuration."""
    descriptions = {
        1: "L1: Full human approval required",
        2: "L2: Human notification only",
        3: "L3: Full autonomy with guardrails",
        4: "L4: Advanced autonomy",
        5: "L5: Maximum autonomy (experimental)"
    }
    return {
        "level": settings.autonomy_level,
        "hitl_required": settings.hitl_approval_required,
        "description": descriptions.get(settings.autonomy_level, "Unknown"),
    }


# Initialize logging on import
configure_logging()

# Log startup configuration
logger.info(
    "Environment configured",
    extra={
        "env": settings.app_env,
        "exchange": settings.exchange,
        "testnet": settings.exchange_testnet,
        "autonomy_level": settings.autonomy_level,
        "hitl_required": settings.hitl_approval_required,
        "paper_trading": is_paper_trading(),
    },
)

# Validate configuration
try:
    validate_configuration()
except ValueError as exc:
    logger.error("Configuration error", exc_info=exc)
    if settings.app_env == "production":
        raise
