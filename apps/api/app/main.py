"""FastAPI application entry point."""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api import health as health_module
from app.api.v1 import api_router
from app.api.v1 import webhooks as webhooks_module
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import PrometheusMiddleware, metrics_response
from app.core.subdomains import extract_subdomain
from app.db.session import SessionLocal
from app.models import Tenant
from sqlalchemy import select
from app.services.llm import AgentLLMError, ChatGPTOAuthError  # noqa: F401
from app.services.storage import ensure_bucket

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
            environment=settings.app_env,
            release=app.version,
            send_default_pii=False,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                CeleryIntegration(),
            ],
        )
    try:
        ensure_bucket()
    except Exception:  # noqa: BLE001
        log.warning("storage_bucket_unreachable")
    log.info("api_started", env=settings.app_env)
    yield


app = FastAPI(
    title="Legal AI OS — Saudi Edition",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ----- Middleware ------------------------------------------------------------

app.add_middleware(PrometheusMiddleware)

# Build CORS origin allowlist. `app_base_url` covers the marketing/auth root;
# `*.<base_domain>` covers every tenant dashboard. Origin regex is escaped so
# `legalai.sa` doesn't match `legalai-sa.com`.
_cors_kwargs: dict = {
    "allow_origins": [settings.app_base_url, "http://localhost:3030"],
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
    "expose_headers": ["X-Request-Id"],
}
if settings.enable_subdomain_cors and settings.base_domain:
    import re as _re

    base_escaped = _re.escape(settings.base_domain)
    # https?://anything.<base>(:port)?  — allows tenant subdomains over either scheme.
    _cors_kwargs["allow_origin_regex"] = (
        rf"https?://[A-Za-z0-9-]+\.{base_escaped}(:\d+)?"
    )

app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.middleware("http")
async def resolve_subdomain(request: Request, call_next):
    """Look up the tenant for the request's subdomain (if any).

    On `acme.legalai.sa`, this stamps `request.state.subdomain` = `"acme"`
    and `request.state.subdomain_tenant_id` = the matching tenant's UUID.
    The auth dep then enforces that the JWT's tenant matches.

    Skipped when:
      - BASE_DOMAIN isn't set (local dev)
      - Host is the apex / `www` / a reserved label
      - No tenant claims that subdomain
    """
    request.state.subdomain = None
    request.state.subdomain_tenant_id = None
    if settings.base_domain:
        # Trust X-Forwarded-Host first (we sit behind nginx in production).
        host = request.headers.get("x-forwarded-host") or request.headers.get(
            "host", ""
        )
        sub = extract_subdomain(host, settings.base_domain)
        if sub:
            request.state.subdomain = sub
            db = SessionLocal()
            try:
                tenant = db.execute(
                    select(Tenant).where(Tenant.subdomain == sub)
                ).scalar_one_or_none()
                if tenant is not None:
                    request.state.subdomain_tenant_id = tenant.id
            finally:
                db.close()
    return await call_next(request)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Bind structured-log + Sentry context for the whole request lifecycle.

    On every request we stamp a `request_id` into both structlog and Sentry.
    Once the deps chain resolves the user, the route attaches `tenant_id` +
    `user_id` to `request.state`; we retro-bind those onto the access log
    after the response so they show up alongside status + duration.
    """
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )
    if settings.sentry_dsn:
        sentry_sdk.set_tag("request_id", request_id)
        sentry_sdk.set_tag("route", request.url.path)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except ChatGPTOAuthError as exc:
        # AI provider auth failure → 502 with a clear message so the
        # dashboard knows to surface a "refresh your token" prompt.
        log.warning("llm_auth_failed")
        if settings.sentry_dsn:
            sentry_sdk.capture_exception(exc)
        return JSONResponse(
            {
                "detail": (
                    "AI provider authentication failed. The ChatGPT OAuth "
                    "token is expired or invalid — refresh it from the "
                    "admin panel and retry."
                ),
                "request_id": request_id,
            },
            status_code=502,
        )
    except Exception as exc:
        log.exception("unhandled_error")
        if settings.sentry_dsn:
            sentry_sdk.capture_exception(exc)
        return JSONResponse(
            {"detail": "Internal server error", "request_id": request_id},
            status_code=500,
        )
    response.headers["x-request-id"] = request_id

    tenant_id = getattr(request.state, "tenant_id", None)
    user_id = getattr(request.state, "user_id", None)
    if tenant_id:
        structlog.contextvars.bind_contextvars(tenant_id=str(tenant_id))
        if settings.sentry_dsn:
            sentry_sdk.set_tag("tenant_id", str(tenant_id))
    if user_id:
        structlog.contextvars.bind_contextvars(user_id=str(user_id))
        if settings.sentry_dsn:
            sentry_sdk.set_user({"id": str(user_id)})

    log.info(
        "request",
        status=response.status_code,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return response


# ----- Routes ----------------------------------------------------------------


@app.get("/health", include_in_schema=False)
def legacy_health(response: Response) -> dict:
    """Backwards-compatible health endpoint (alias of /health/ready)."""
    return health_module.ready(response)


# --- Exception handlers -----------------------------------------------------

@app.exception_handler(AgentLLMError)
async def _agent_llm_failed(request: Request, exc: AgentLLMError) -> JSONResponse:
    """Surface AI-provider auth/quota failure as 502 instead of a generic 500.

    Covers both ChatGPT OAuth (Codex backend) and Gemini (Code Assist) — the
    base ``AgentLLMError`` catches whichever provider is currently configured.
    """
    log.warning(
        "llm_auth_failed",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        provider=settings.agent_provider,
    )
    if exc.status_code == 401:
        if settings.agent_provider == "gemini":
            detail = (
                "Gemini auth failed. Re-run `python scripts/gemini_oauth_login.py` "
                "to refresh the OAuth token."
            )
        else:
            detail = (
                "ChatGPT OAuth token is expired or invalid — refresh it from "
                "the admin panel and retry."
            )
    else:
        detail = f"AI provider error ({exc.status_code or 'no status'}): {exc}"
    return JSONResponse(status_code=502, content={"detail": detail})


app.include_router(health_module.router, prefix="/health", tags=["health"])
app.include_router(api_router)
app.include_router(webhooks_module.router, prefix="/webhooks", tags=["webhooks"])


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return metrics_response()
