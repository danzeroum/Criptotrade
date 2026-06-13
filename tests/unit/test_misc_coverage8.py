"""Eighth batch — API routes, dependency functions, and small edge cases."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


# ── Helper: synthetic OHLCV with enough candles for TA ───────────────────────

def _ohlcv(n: int = 200) -> list:
    ts = 1_700_000_000_000
    result = []
    import math
    for i in range(n):
        close = 50_000.0 + 200 * math.sin(2 * math.pi * i / 50)
        result.append([
            ts + i * 3_600_000,
            close - 200,
            close + 300,
            close - 400,
            close,
            100.0 + i,
        ])
    return result


def _mock_client() -> MagicMock:
    mc = MagicMock()
    mc.fetch_ohlcv = AsyncMock(return_value=_ohlcv(200))
    mc.fetch_ticker = AsyncMock(return_value={
        "last": 50_100.0,
        "bid": 50_090.0,
        "ask": 50_110.0,
        "timestamp": 1_700_000_000_000,
    })
    return mc


# ── API — health endpoint ─────────────────────────────────────────────────────

def test_health_endpoint(tmp_path, monkeypatch):
    """Line 239: GET /health → {'status': 'healthy'}."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ── API — HTTP exception handler (404 non-dict path) ─────────────────────────

def test_http_exception_handler_404_non_dict(tmp_path, monkeypatch):
    """Lines 260-268: framework 404 (string detail) → custom not_found body."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.get("/v1/endpoint_that_does_not_exist_xyz")
    assert r.status_code == 404
    body = r.json()
    assert body.get("error") == "not_found"


# ── API — validation error handler ───────────────────────────────────────────

def test_validation_error_handler(tmp_path, monkeypatch):
    """Lines 243-254: bad request body → RequestValidationError → 422 with error field."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    # POST to orders with completely wrong body triggers RequestValidationError
    r = client.post("/v1/orders", json={"bogus": "data"})
    assert r.status_code == 422
    body = r.json()
    assert body.get("error") == "validation_error"


# ── API — agents routes ────────────────────────────────────────────────────────

def test_api_list_agents(tmp_path, monkeypatch):
    """Line 27: GET /v1/agents → list of agent status objects."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/agents")
    assert r.status_code == 200
    data = r.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0


def test_api_get_agent_config_known(tmp_path, monkeypatch):
    """Lines 39-49: GET /v1/agents/{id}/config → config object for known agent."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/agents/risk/config")
    assert r.status_code == 200
    assert r.json()["data"]["id"] == "risk"


def test_api_get_agent_config_unknown(tmp_path, monkeypatch):
    """Lines 40-48: unknown agent_id → 404 with agent_not_found."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/agents/no_such_agent_xyz/config")
    assert r.status_code == 404
    assert r.json().get("error") == "agent_not_found"


def test_api_get_agent_not_implemented(tmp_path, monkeypatch):
    """Lines 71-79: unimplemented (stub) agent → 501 Not Implemented."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    # "recovery" is an unimplemented stub in AGENT_REGISTRY
    r = client.get("/v1/agents/recovery")
    assert r.status_code == 501
    assert r.json().get("error") == "not_implemented"


def test_api_get_agent_not_found(tmp_path, monkeypatch):
    """Lines 62-69: GET /v1/agents/{unknown} → 404."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/agents/does_not_exist")
    assert r.status_code == 404
    assert r.json().get("error") == "agent_not_found"


# ── API — metrics routes ───────────────────────────────────────────────────────

def test_api_get_metrics(tmp_path, monkeypatch):
    """Lines 30-31: GET /v1/metrics → portfolio KPIs."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/metrics")
    assert r.status_code == 200
    assert "total_trades" in r.json()["data"]


def test_api_get_equity(tmp_path, monkeypatch):
    """Lines 50-71: GET /v1/metrics/equity → equity time series (empty → default point)."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/metrics/equity")
    assert r.status_code == 200
    points = r.json()["data"]
    assert isinstance(points, list)
    assert len(points) >= 1


# ── API — alerts history ───────────────────────────────────────────────────────

def test_api_alerts_history(tmp_path, monkeypatch):
    """Lines 76-82: GET /v1/alerts/history → paginated alert list."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/alerts/history")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


def test_alerts_json_helper():
    """Lines 86-88: _json serialises a dict to JSON string."""
    from src.api.routes.alerts import _json

    result = _json({"message": "ok", "count": 1})
    assert '"message"' in result
    assert '"ok"' in result


# ── API — orders list ──────────────────────────────────────────────────────────

def test_api_list_orders(tmp_path, monkeypatch):
    """Lines 44-49: GET /v1/orders → list (possibly empty)."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/orders")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


# ── API — risk routes ──────────────────────────────────────────────────────────

def test_api_risk_protections(tmp_path, monkeypatch):
    """Lines 81-113: GET /v1/risk/protections → daily/weekly/monthly protections."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/risk/protections")
    assert r.status_code == 200
    data = r.json()["data"]
    assert isinstance(data, list)
    assert any(p["scope"] == "daily" for p in data)


def test_api_risk_circuit_breaker(tmp_path, monkeypatch):
    """Lines 125-155: GET /v1/risk/circuit-breaker → circuit breaker status."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/risk/circuit-breaker")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "status" in data


def test_api_risk_kelly(tmp_path, monkeypatch):
    """Lines 167-172: GET /v1/risk/kelly → insufficient data (< 10 trades)."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/risk/kelly")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["data_quality"] == "insufficient"


def test_api_risk_config(tmp_path, monkeypatch):
    """Lines 222-229: GET /v1/risk/config → risk configuration from yaml."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    client = TestClient(create_app())
    r = client.get("/v1/risk/config")
    assert r.status_code == 200


# ── API — market routes (mocked exchange client) ───────────────────────────────

def _app_with_mock_exchange(tmp_path, monkeypatch):
    from src.api.main import create_app
    from src.api.deps import get_exchange_client
    from src.core.db import init_db

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    init_db()
    app = create_app()
    mc = _mock_client()
    app.dependency_overrides[get_exchange_client] = lambda: mc
    return app


def test_market_candles(tmp_path, monkeypatch):
    """Lines 138-141: GET /v1/market/BTC-USDT/candles → list of OHLCV candles."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/BTC-USDT/candles")
    assert r.status_code == 200
    data = r.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0


def test_market_ticker(tmp_path, monkeypatch):
    """Lines 86-124: GET /v1/market/BTC-USDT/ticker → 24h price stats."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/BTC-USDT/ticker")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "last" in data
    assert "volume_24h" in data


def test_market_indicators(tmp_path, monkeypatch):
    """Lines 155-194: GET /v1/market/BTC-USDT/indicators → technical indicators."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/BTC-USDT/indicators")
    assert r.status_code == 200


def test_market_regime(tmp_path, monkeypatch):
    """Lines 208-232: GET /v1/market/BTC-USDT/regime → market regime."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/BTC-USDT/regime")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "regime" in data


def test_market_levels(tmp_path, monkeypatch):
    """Lines 246-274: GET /v1/market/BTC-USDT/levels → S/R levels and Fibonacci."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/BTC-USDT/levels")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "support" in data
    assert "fib" in data


def test_market_volume_profile(tmp_path, monkeypatch):
    """Lines 289-330: GET /v1/market/BTC-USDT/volume-profile → VP analysis."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/BTC-USDT/volume-profile")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "poc" in data


def test_market_patterns(tmp_path, monkeypatch):
    """Lines 344-361: GET /v1/market/BTC-USDT/patterns → pattern list."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/BTC-USDT/patterns")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


def test_market_signal(tmp_path, monkeypatch):
    """Lines 375-453: GET /v1/market/BTC-USDT/signal → trading signal."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/BTC-USDT/signal")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "action" in data
    assert data["action"] in ("buy", "sell", "hold")


def test_market_invalid_pair(tmp_path, monkeypatch):
    """Lines 54-63: _decode_pair rejects unknown pair → 422 invalid_pair."""
    from fastapi.testclient import TestClient

    app = _app_with_mock_exchange(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get("/v1/market/UNKNOWN-TOKEN/candles")
    assert r.status_code == 422
    body = r.json()
    assert body.get("error") == "invalid_pair"


# ── Deps — _initial_capital / _initial_level direct coverage ─────────────────

def test_initial_capital_default(monkeypatch):
    """Lines 23-24: no env var → parses default '10000' → 10_000.0."""
    monkeypatch.delenv("INITIAL_CAPITAL", raising=False)
    from src.api.deps import _initial_capital
    assert _initial_capital() == 10_000.0


def test_initial_capital_invalid_env(monkeypatch):
    """Lines 25-26: INITIAL_CAPITAL='bad' → ValueError → returns 10_000.0."""
    monkeypatch.setenv("INITIAL_CAPITAL", "not_a_number")
    from src.api.deps import _initial_capital
    assert _initial_capital() == 10_000.0


def test_initial_level_default(monkeypatch):
    """Line 32: AUTONOMY_LEVEL not set → returns DEFAULT_LEVEL."""
    monkeypatch.delenv("AUTONOMY_LEVEL", raising=False)
    from src.api.deps import _initial_level, DEFAULT_LEVEL
    assert _initial_level() == DEFAULT_LEVEL


def test_initial_level_invalid_string(monkeypatch):
    """Lines 35-36: AUTONOMY_LEVEL='bad' → ValueError → returns DEFAULT_LEVEL."""
    monkeypatch.setenv("AUTONOMY_LEVEL", "not_a_level")
    from src.api.deps import _initial_level, DEFAULT_LEVEL
    assert _initial_level() == DEFAULT_LEVEL


def test_initial_level_out_of_range(monkeypatch):
    """Line 37: level out of [MIN_LEVEL, MAX_LEVEL] → returns DEFAULT_LEVEL."""
    monkeypatch.setenv("AUTONOMY_LEVEL", "999")
    from src.api.deps import _initial_level, DEFAULT_LEVEL
    assert _initial_level() == DEFAULT_LEVEL


# ── Deps — cached dependency functions direct calls ───────────────────────────

def test_get_ledger_direct(tmp_path, monkeypatch):
    """Line 42: get_ledger() creates and returns a TradingLedger."""
    from src.api.deps import get_ledger, reset_singletons

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    reset_singletons()
    ledger = get_ledger()
    assert ledger is not None
    reset_singletons()


def test_get_alert_store_direct(tmp_path, monkeypatch):
    """Line 47: get_alert_store() creates and returns an AlertStore."""
    from src.api.deps import get_alert_store, reset_singletons

    reset_singletons()
    store = get_alert_store()
    assert store is not None
    reset_singletons()


def test_get_alert_bus_direct():
    """Line 52: get_alert_bus() creates and returns an AlertBus."""
    from src.api.deps import get_alert_bus, reset_singletons

    reset_singletons()
    bus = get_alert_bus()
    assert bus is not None
    reset_singletons()


def test_get_metrics_calculator_direct(tmp_path, monkeypatch):
    """Line 96: get_metrics_calculator() creates PortfolioMetricsCalculator."""
    from src.api.deps import get_metrics_calculator, reset_singletons

    monkeypatch.setenv("LEDGER_DIR", str(tmp_path))
    reset_singletons()
    calc = get_metrics_calculator()
    assert calc is not None
    reset_singletons()


# ── ParallelResourceManager — awaitable (non-callable) task ──────────────────

@pytest.mark.asyncio
async def test_parallel_execute_awaitable_task():
    """Line 27: task is awaitable but not callable → await task (not task())."""
    from src.parallel.resource_manager import ParallelResourceManager

    manager = ParallelResourceManager()

    async def _coro():
        return "awaitable_result"

    # Pass the coroutine object directly (not the function)
    results = await manager.execute_parallel_with_limits([_coro()])
    assert results == ["awaitable_result"]


# ── ResilientPromptChain — max_retries=0 triggers inner-loop empty arc ────────

@pytest.mark.asyncio
async def test_resilient_chain_max_retries_zero():
    """Line 23->22: range(1,1) is empty → inner loop never runs → outer loop proceeds."""
    from src.chains.resilient_chain import ResilientPromptChain, ChainStep

    executed = []
    step1 = ChainStep(name="s1", execute=lambda x: executed.append("s1") or x + 10)
    step2 = ChainStep(name="s2", execute=lambda x: executed.append("s2") or x * 2)
    chain = ResilientPromptChain(steps=[step1, step2], max_retries=0)
    result = await chain.execute_with_checkpoints(7)
    # Steps are never executed (inner loop range is empty for each step)
    assert executed == []
    assert result == 7  # initial_input unchanged


# ── RiskAgent — position_size > max triggers issues (line 70) ─────────────────

@pytest.mark.asyncio
async def test_risk_agent_position_size_too_large():
    """Line 70: position_size_pct > max_position_size_pct → issues.append."""
    from src.agents.risk_agent import RiskAgent

    agent = RiskAgent()  # max_position_size_pct = 5.0
    signal = {
        "entry_price": 50_000.0,
        "stop_loss": 49_900.0,
        "position_size_pct": 8.0,  # 8% > 5% limit
        "take_profit": 51_000.0,
    }
    result = await agent._validate_signal(signal, {})
    assert any("Position size" in i for i in result["issues"])
    assert result["approved"] is False


# ── VectorDBClient — get_or_create_collection path (lines 27-30) ──────────────

def test_vectordb_get_or_create_collection():
    """Lines 27-30: backend with only get_or_create_collection → 3rd branch taken."""
    from src.tools.rag_tool import VectorDBClient

    # Restrict spec so hasattr returns False for similarity_search and query
    mock_backend = MagicMock(spec=["get_or_create_collection"])
    mock_collection = MagicMock()
    mock_collection.query.return_value = {"documents": [["doc_a", "doc_b"]]}
    mock_backend.get_or_create_collection.return_value = mock_collection

    client = VectorDBClient(mock_backend)
    result = client.similarity_search("query text", k=2)
    assert result == ["doc_a", "doc_b"]
    mock_backend.get_or_create_collection.assert_called_once_with("btf-default")


def test_vectordb_get_or_create_collection_cached():
    """Line 27: _collection already set → get_or_create_collection not called again."""
    from src.tools.rag_tool import VectorDBClient

    mock_backend = MagicMock(spec=["get_or_create_collection"])
    mock_collection = MagicMock()
    mock_collection.query.return_value = {"documents": [["cached_doc"]]}
    mock_backend.get_or_create_collection.return_value = mock_collection

    client = VectorDBClient(mock_backend)
    # Pre-populate _collection so the `if self._collection is None` branch is False
    client._collection = mock_collection

    result = client.similarity_search("second query", k=1)
    assert result == ["cached_doc"]
    mock_backend.get_or_create_collection.assert_not_called()
