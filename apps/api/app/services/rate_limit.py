"""Redis-backed sliding-window rate limiter + login lockout helpers.

Two public APIs:

  - rate_limit_check(bucket, identifier, limit, window_seconds)
    Returns (allowed: bool, remaining: int, reset_seconds: int). Use as a
    standalone gate inside endpoints.

  - lockout_register_failure / lockout_is_locked / lockout_clear
    Track failed login attempts and lock an account temporarily after too
    many in a row. Locks survive process restarts because they're in Redis.

Both degrade gracefully when Redis is unreachable — a missing Redis is
strictly worse than a Redis with stale state, but neither should kill the
auth flow.
"""
from __future__ import annotations

from time import time
from typing import Iterable

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis

log = get_logger(__name__)


# =============================================================================
# Rate limiter
# =============================================================================


def rate_limit_check(
    *,
    bucket: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int, int]:
    """Increment the counter for (bucket, identifier) and check against limit.

    Returns (allowed, remaining, reset_seconds). When Redis is down, returns
    (True, limit, window_seconds) — fail-open for availability.
    """
    if limit <= 0 or window_seconds <= 0:
        return True, limit, window_seconds
    key = f"rl:{bucket}:{identifier}"
    try:
        r = get_redis()
        pipe = r.pipeline(transaction=False)
        pipe.incr(key, 1)
        pipe.expire(key, window_seconds, nx=True)
        pipe.ttl(key)
        count, _, ttl = pipe.execute()
    except Exception as exc:  # noqa: BLE001
        log.warning("rate_limit_redis_unavailable", error=str(exc), bucket=bucket)
        return True, limit, window_seconds

    count = int(count or 0)
    ttl = int(ttl or window_seconds)
    if ttl < 0:
        ttl = window_seconds
    remaining = max(0, limit - count)
    allowed = count <= limit
    return allowed, remaining, ttl


def rate_limit_keys_for_request(
    request_ip: str | None,
    user_id: str | None,
    tenant_id: str | None,
) -> Iterable[str]:
    """Compose useful identifiers from a request. Skip Nones."""
    if request_ip:
        yield f"ip:{request_ip}"
    if user_id:
        yield f"user:{user_id}"
    if tenant_id:
        yield f"tenant:{tenant_id}"


# =============================================================================
# Login lockout
# =============================================================================


def _lockout_key(email: str) -> str:
    return f"lockout:login:{email.lower()}"


def lockout_register_failure(email: str) -> int:
    """Increment the lockout counter. If the new count >= max attempts,
    extend the TTL for the lockout window. Returns current attempt count."""
    if not email:
        return 0
    key = _lockout_key(email)
    try:
        r = get_redis()
        pipe = r.pipeline(transaction=False)
        pipe.incr(key, 1)
        pipe.expire(key, settings.login_lockout_window_seconds, nx=True)
        count, _ = pipe.execute()
        count = int(count or 0)
        if count >= settings.login_lockout_max_attempts:
            r.expire(key, settings.login_lockout_window_seconds)
        return count
    except Exception:  # noqa: BLE001
        return 0


def lockout_is_locked(email: str) -> tuple[bool, int]:
    """Returns (locked, retry_after_seconds)."""
    if not email:
        return False, 0
    key = _lockout_key(email)
    try:
        r = get_redis()
        count = int(r.get(key) or 0)
        if count < settings.login_lockout_max_attempts:
            return False, 0
        ttl = int(r.ttl(key) or 0)
        return True, max(ttl, 0)
    except Exception:  # noqa: BLE001
        return False, 0


def lockout_clear(email: str) -> None:
    if not email:
        return
    try:
        get_redis().delete(_lockout_key(email))
    except Exception:  # noqa: BLE001
        pass
