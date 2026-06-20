"""X-Request-ID correlation middleware (v3)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import create_app


def test_response_carries_a_request_id():
    r = TestClient(create_app()).get("/health")
    assert r.headers.get("X-Request-ID")


def test_inbound_request_id_is_echoed():
    r = TestClient(create_app()).get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


def test_each_request_gets_a_distinct_id():
    client = TestClient(create_app())
    a = client.get("/health").headers["X-Request-ID"]
    b = client.get("/health").headers["X-Request-ID"]
    assert a != b
