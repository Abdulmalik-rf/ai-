"""Lazy, process-wide Redis client.

Used by the rate limiter and login-lockout helpers. We keep one client per
process; the underlying connection pool is managed by redis-py.

If REDIS_URL is unreachable, callers degrade gracefully — rate limits become
permissive, lockouts no-op. We never hard-fail a request because Redis is
having a moment.
"""
from __future__ import annotations

from typing import Optional

import redis

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
            health_check_interval=30,
        )
    return _client


def is_healthy() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:  # noqa: BLE001
        return False
