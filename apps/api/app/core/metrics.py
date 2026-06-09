"""Prometheus metrics — request, agent, db pool, billing.

A single registry exported at /metrics. The middleware below stamps
per-request metrics; long-lived gauges sample on every scrape.

Cardinality discipline: we tag with `route` (the FastAPI path template, NOT
the URL — `/v1/cases/{case_id}` not `/v1/cases/abc-123`) and `method`. Never
tag with `tenant_id` or `user_id` — that explodes Prometheus.
"""
from __future__ import annotations

import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# Process-wide registry. Keep one — multiple registries fragment scrapes.
REGISTRY = CollectorRegistry(auto_describe=True)


# --- HTTP -------------------------------------------------------------------

http_requests_total = Counter(
    "legalai_http_requests_total",
    "HTTP requests by route, method, status",
    ["route", "method", "status"],
    registry=REGISTRY,
)

http_request_duration = Histogram(
    "legalai_http_request_duration_seconds",
    "HTTP request duration",
    ["route", "method"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)


# --- Agent ------------------------------------------------------------------

agent_turns_total = Counter(
    "legalai_agent_turns_total",
    "Agent turns by scope (lawyer | intake) and outcome",
    ["scope", "outcome"],  # outcome: ok | ceiling | error
    registry=REGISTRY,
)

agent_turn_duration = Histogram(
    "legalai_agent_turn_duration_seconds",
    "Agent loop end-to-end latency",
    ["scope"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
    registry=REGISTRY,
)

agent_tool_calls_total = Counter(
    "legalai_agent_tool_calls_total",
    "Tools the agent invoked across all turns",
    ["scope", "tool"],
    registry=REGISTRY,
)

agent_token_errors_total = Counter(
    "legalai_agent_token_errors_total",
    "ChatGPT OAuth token failures (401 / network / unknown)",
    ["kind"],  # expired | network | other
    registry=REGISTRY,
)


# --- Billing / lifecycle ----------------------------------------------------

billing_events_total = Counter(
    "legalai_billing_events_total",
    "Billing webhook + lifecycle events",
    ["provider", "event"],  # event: invoice_paid | invoice_failed | trial_ended | …
    registry=REGISTRY,
)


# --- DB pool ----------------------------------------------------------------

db_pool_checked_out = Gauge(
    "legalai_db_pool_checked_out",
    "Connections currently checked out of the engine pool",
    registry=REGISTRY,
)
db_pool_in_use = Gauge(
    "legalai_db_pool_size",
    "Configured base pool size",
    registry=REGISTRY,
)


# --- WhatsApp bridge --------------------------------------------------------

whatsapp_sessions_total = Gauge(
    "legalai_whatsapp_sessions_total",
    "Per-tenant WhatsApp session counts by status",
    ["status"],
    registry=REGISTRY,
)


# --- Middleware -------------------------------------------------------------


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Stamp every HTTP request with a counter + duration histogram."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            # `route.path` gives the path template. When no match (404), fall
            # back to the raw URL path — high-cardinality but rare.
            route = request.scope.get("route")
            route_path = getattr(route, "path", None) or request.url.path
            method = request.method
            status_code = str(response.status_code if response else 500)
            duration = time.perf_counter() - started
            http_requests_total.labels(
                route=route_path, method=method, status=status_code
            ).inc()
            http_request_duration.labels(route=route_path, method=method).observe(
                duration
            )


# --- /metrics endpoint ------------------------------------------------------


def metrics_response() -> Response:
    """Serialize the registry to text/plain;version=0.0.4."""
    # Sample the DB pool gauge before scraping so it's fresh.
    try:
        from app.db.session import engine

        pool = engine.pool
        db_pool_checked_out.set(pool.checkedout())
        db_pool_in_use.set(pool.size())
    except Exception:  # noqa: BLE001
        pass
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
