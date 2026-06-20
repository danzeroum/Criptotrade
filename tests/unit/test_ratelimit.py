"""Pluggable rate-limit backends (v2 scale-readiness)."""
from __future__ import annotations

from src.core.ratelimit import (
    InMemoryRateLimiter,
    RedisFixedWindowLimiter,
    build_rate_limiter,
    make_redis_client,
)


def test_inmemory_blocks_after_limit():
    rl = InMemoryRateLimiter(window_seconds=60)
    assert rl.allow("k", 2) is True
    assert rl.allow("k", 2) is True
    assert rl.allow("k", 2) is False  # 3rd hit exceeds limit of 2
    assert rl.allow("other", 2) is True  # independent key


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, int] = {}
        self.ttl: dict[str, int] = {}

    def incr(self, key):
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def pexpire(self, key, ms):
        self.ttl[key] = ms


def test_redis_fixed_window_counts_and_expires():
    fake = _FakeRedis()
    rl = RedisFixedWindowLimiter(fake, window_seconds=60)
    assert rl.allow("k", 2) is True
    assert rl.allow("k", 2) is True
    assert rl.allow("k", 2) is False
    # TTL set once, on the first hit of the window.
    assert fake.ttl["rl:k"] == 60_000


def test_redis_limiter_fails_open_on_backend_error():
    class _Boom:
        def incr(self, key):
            raise RuntimeError("redis down")

        def pexpire(self, key, ms):
            pass

    rl = RedisFixedWindowLimiter(_Boom(), window_seconds=60)
    assert rl.allow("k", 1) is True  # never block when the backend is broken


def test_build_rate_limiter_defaults_to_in_memory(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert isinstance(build_rate_limiter(60), InMemoryRateLimiter)


def test_make_redis_client_returns_none_without_server(monkeypatch):
    # redis package absent (or no server) -> graceful None, caller falls back.
    assert make_redis_client("redis://localhost:6379/0") is None
