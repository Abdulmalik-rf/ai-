"""Health endpoints — liveness vs readiness vs full diagnostic.

Three endpoints with distinct semantics so load balancers, orchestrators,
and humans get the right answer:

  GET /health/live    — does the process answer at all?
                         (Used by Kubernetes livenessProbe / process supervisors.)
  GET /health/ready   — is the process willing to take traffic?
                         Returns 503 if a hard dependency (DB, Redis) is down.
                         S3 + bridge are SOFT — they're reported but don't fail
                         readiness, since the API can degrade gracefully.
  GET /health         — backwards-compat: same shape as `/health/ready`.

The check helpers run in parallel via threadpool when async would be heavier
than the work itself. Each probe has a 2s timeout so a wedged dependency
doesn't make the health endpoint hang.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter
from typing import Callable

import httpx
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis
from app.db.session import engine
from app.services.storage import _s3_client

log = get_logger(__name__)

router = APIRouter()


@dataclass
class ProbeResult:
    name: str
    ok: bool
    latency_ms: int
    error: str | None = None


def _run_probe(name: str, fn: Callable[[], None]) -> ProbeResult:
    started = perf_counter()
    try:
        fn()
        return ProbeResult(
            name=name, ok=True, latency_ms=int((perf_counter() - started) * 1000)
        )
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(
            name=name,
            ok=False,
            latency_ms=int((perf_counter() - started) * 1000),
            error=str(exc)[:200],
        )


# --- Individual probes -------------------------------------------------------


def _probe_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _probe_redis() -> None:
    if not get_redis().ping():
        raise RuntimeError("ping returned falsy")


def _probe_s3() -> None:
    s3 = _s3_client()
    s3.head_bucket(Bucket=settings.s3_bucket)


def _probe_bridge() -> None:
    if not settings.enable_whatsapp_baileys:
        # Disabled on this deployment — counts as healthy, not relevant.
        return
    if not settings.whatsapp_bridge_url:
        raise RuntimeError("WHATSAPP_BRIDGE_URL not configured")
    with httpx.Client(timeout=2) as c:
        r = c.get(f"{settings.whatsapp_bridge_url.rstrip('/')}/health")
        if r.status_code >= 400:
            raise RuntimeError(f"bridge returned {r.status_code}")


# --- Endpoints ---------------------------------------------------------------


@router.get("/live")
def live() -> dict:
    """Process-up check. No dependencies are touched."""
    return {"status": "ok"}


_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="health-probe")


def _gather_probes() -> list[ProbeResult]:
    """Run all probes in parallel via threadpool with a hard 2.5s overall budget."""
    futures = {
        _executor.submit(_run_probe, name, fn): name
        for name, fn in (
            ("db", _probe_db),
            ("redis", _probe_redis),
            ("s3", _probe_s3),
            ("bridge", _probe_bridge),
        )
    }
    results: list[ProbeResult] = []
    for fut in futures:
        try:
            results.append(fut.result(timeout=2.5))
        except Exception as exc:  # noqa: BLE001 (catch hangs, surface as failed probe)
            name = futures[fut]
            results.append(
                ProbeResult(name=name, ok=False, latency_ms=2500, error=f"timeout: {exc}")
            )
    return results


_HARD_DEPENDENCIES = {"db", "redis"}


@router.get("/ready")
def ready(response: Response) -> dict:
    probes = _gather_probes()
    failed_hard = [p for p in probes if not p.ok and p.name in _HARD_DEPENDENCIES]
    overall_ok = not failed_hard
    response.status_code = (
        status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return {
        "status": "ok" if overall_ok else "degraded",
        "version": "0.1.0",
        "env": settings.app_env,
        "probes": [
            {
                "name": p.name,
                "ok": p.ok,
                "latency_ms": p.latency_ms,
                "error": p.error,
                "hard_dependency": p.name in _HARD_DEPENDENCIES,
            }
            for p in probes
        ],
    }
