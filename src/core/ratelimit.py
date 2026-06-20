"""Pluggable rate-limit backends.

The default in-memory limiter is per-process — correct for a single API
container. To scale the API horizontally (multiple replicas behind a load
balancer) the counter must be shared, so a Redis fixed-window limiter is provided
and selected automatically when ``REDIS_URL`` is set and the ``redis`` package is
installed. Everything fails open: if Redis is misconfigured or unreachable the
middleware falls back to in-memory counting rather than blocking traffic.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class RateLimiter(Protocol):
    """Counts a hit for ``key`` and returns True if it is still within ``limit``."""

    def allow(self, key: str, limit: int) -> bool: ...


class InMemoryRateLimiter:
    """Per-process sliding-window limiter (default; not shared across replicas)."""

    def __init__(self, window_seconds: float) -> None:
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = {}

    def allow(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        bucket = [t for t in self._buckets.get(key, []) if t > cutoff]
        if len(bucket) >= limit:
            self._buckets[key] = bucket
            return False
        bucket.append(now)
        self._buckets[key] = bucket
        return True


class RedisFixedWindowLimiter:
    """Shared fixed-window limiter backed by Redis (works across API replicas).

    Uses ``INCR`` + a one-window TTL on first hit. ``client`` is any object with
    ``incr`` and ``pexpire`` (the real ``redis.Redis``, or a fake in tests), so
    this class is unit-testable without a live Redis.
    """

    def __init__(self, client: Any, window_seconds: float, namespace: str = "rl") -> None:
        self._client = client
        self._window_ms = int(window_seconds * 1000)
        self._ns = namespace

    def allow(self, key: str, limit: int) -> bool:
        redis_key = f"{self._ns}:{key}"
        try:
            count = int(self._client.incr(redis_key))
            if count == 1:
                self._client.pexpire(redis_key, self._window_ms)
            return count <= limit
        except Exception:  # pragma: no cover - fail open on backend errors
            logger.warning("Redis rate-limit backend error; allowing request", exc_info=True)
            return True


def make_redis_client(url: str) -> Optional[Any]:
    """Build a Redis client from ``url`` (lazy import). Returns None if unavailable."""
    try:
        import redis  # type: ignore
    except ImportError:
        logger.warning("REDIS_URL set but 'redis' package not installed; using in-memory limiter")
        return None
    try:
        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return client
    except Exception:  # pragma: no cover - network/config guard
        logger.warning("Could not connect to Redis at %s; using in-memory limiter", url)
        return None


def build_rate_limiter(window_seconds: float) -> RateLimiter:
    """Select the rate-limit backend from the environment (Redis if configured)."""
    url = os.getenv("REDIS_URL", "").strip()
    if url:
        client = make_redis_client(url)
        if client is not None:
            logger.info("Rate limiting backed by Redis (shared across replicas)")
            return RedisFixedWindowLimiter(client, window_seconds)
    return InMemoryRateLimiter(window_seconds)


__all__ = [
    "RateLimiter",
    "InMemoryRateLimiter",
    "RedisFixedWindowLimiter",
    "make_redis_client",
    "build_rate_limiter",
]
