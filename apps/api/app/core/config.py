"""Typed settings loaded from environment.

Every other module reads from `settings` — never from `os.environ` directly.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Legal AI OS"
    app_base_url: str = "http://localhost:3030"
    api_base_url: str = "http://localhost:8000"

    # Wildcard DNS root for tenant subdomains. In production set this to
    # your registered domain (e.g. `legalai.sa`); the backend will then
    # resolve any `*.legalai.sa` request to its tenant via the
    # `tenants.subdomain` column. Empty → subdomain resolution is off
    # (useful for `localhost` dev where there's no real DNS).
    base_domain: str = ""
    # Allow CORS from `*.<base_domain>` in addition to `app_base_url`.
    enable_subdomain_cors: bool = True

    # --- Auth ---
    jwt_secret: str = Field(default="change-me", min_length=8)
    jwt_access_ttl_min: int = 30
    jwt_refresh_ttl_days: int = 14
    jwt_algorithm: str = "HS256"

    # Single-use token TTLs.
    email_verification_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 30
    invite_ttl_days: int = 7

    # Login lockout — temporarily refuses login for an email after too many
    # consecutive failures. Counters live in Redis; an attacker who knocks
    # the Redis service offline gets the soft-fail behavior (no lock).
    login_lockout_max_attempts: int = 8
    login_lockout_window_seconds: int = 15 * 60  # 15 min

    # PDPL / right-to-be-forgotten grace windows. Schedule-then-purge so
    # admins can undo, and so we satisfy the legal retention period for
    # audit logs before scrubbing PII.
    account_deletion_grace_days: int = 14
    tenant_deletion_grace_days: int = 30

    # Trial + dunning windows (days after due date / trial end).
    trial_default_length_days: int = 14
    dunning_first_reminder_days: int = 3
    dunning_second_reminder_days: int = 7
    dunning_suspend_after_days: int = 14

    # Saudi Arabia VAT — used by invoice generation.
    vat_rate: float = 0.15
    vat_seller_name: str = "Legal AI OS"
    vat_seller_vat_number: str = ""  # 15-digit ZATCA VAT number when registered
    vat_seller_address_ar: str = "المملكة العربية السعودية"
    vat_seller_address_en: str = "Kingdom of Saudi Arabia"

    # --- Database ---
    database_url: str = "postgresql+psycopg://legalai:legalai@localhost:5432/legalai"
    # Sized for ~10K active users with bursty dashboard traffic. With
    # workers + the API process, expect ~80 concurrent backend connections
    # peak — set Postgres `max_connections` ≥ 200 to leave headroom.
    database_pool_size: int = 20
    database_max_overflow: int = 60
    # Recycle connections so we don't hold stale ones across Postgres restarts
    # / load-balancer drops. Postgres default idle_in_transaction_session_timeout
    # tends to be 0 (off), so we self-recycle every 30 min.
    database_pool_recycle_seconds: int = 1800
    # Don't block forever waiting for a connection slot — fail fast so the
    # client retries instead of stacking requests on a stuck pool.
    database_pool_timeout_seconds: int = 30

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Object storage ---
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "legalai-documents"
    s3_force_path_style: bool = True

    # --- LLM ---
    # `chatgpt-oauth` calls the Codex backend with a ChatGPT Plus session JWT.
    # `gemini`       calls Google's Code Assist API via an OAuth bearer
    #                obtained through scripts/gemini_oauth_login.py.
    # Both expose a Responses-API-compatible `respond()` shape so the agent
    # loop in services/agent.py works regardless of which is selected.
    llm_provider: Literal[
        "openai", "anthropic", "azure-openai", "chatgpt-oauth", "gemini"
    ] = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096

    # --- Agent brain selector ---
    # Which provider drives the multi-step tool-use loop in services/agent.py.
    # Decoupled from `llm_provider` so you can mix-and-match (e.g. Gemini for
    # the agent loop, OpenAI for structured background tasks).
    agent_provider: Literal["chatgpt-oauth", "gemini"] = "chatgpt-oauth"

    # --- ChatGPT OAuth (Codex backend) ---
    # The token MUST be issued for the Codex-CLI client through the OAuth
    # PKCE flow (scripts/chatgpt_codex_oauth.py) — a chatgpt.com/api/auth/session
    # token is issued for a different client_id and the Codex backend 401s it.
    openai_chatgpt_token: str = ""
    openai_chatgpt_model: str = "gpt-5.5"
    openai_chatgpt_effort: Literal["low", "medium", "high"] = "low"
    openai_chatgpt_timeout_s: int = 180
    # Path (relative to apps/api or absolute) to the Codex OAuth creds JSON
    # holding access_token + refresh_token + account_id. When set, the
    # provider prefers it over the static token and auto-refreshes on 401.
    openai_codex_creds_path: str = ""
    # Credentials for the headless auto-login fallback (scripts/*).
    openai_auth_email: str = ""
    openai_auth_password: str = ""

    # --- Gemini (Google OAuth → Code Assist API) ---
    # Credentials live in apps/api/.gemini_oauth.json (in .gitignore),
    # produced by scripts/gemini_oauth_login.py. The provider auto-refreshes
    # the access token via the cached refresh_token, so the file is read/
    # written across the lifetime of the process — never re-run the script
    # unless the refresh_token itself is revoked.
    gemini_creds_path: str = ""  # blank → default to apps/api/.gemini_oauth.json
    gemini_model: str = "gemini-2.5-pro"
    gemini_timeout_s: int = 180
    gemini_thinking_budget: int = -1  # -1 = let model decide; 0 disables thinking

    # --- Embeddings ---
    # `local` runs a sentence-transformers model in-process — no API key needed,
    # works fully offline once the model is downloaded. Useful when the deployment
    # only has a ChatGPT OAuth token (no Platform API key).
    embeddings_provider: Literal["openai", "local"] = "openai"
    embeddings_model: str = "text-embedding-3-large"
    embeddings_dim: int = 3072

    # --- Billing ---
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_basic: str = ""
    stripe_price_pro: str = ""
    stripe_price_enterprise: str = ""
    moyasar_publishable_key: str = ""
    moyasar_secret_key: str = ""
    moyasar_webhook_secret: str = ""

    # --- WhatsApp (Twilio — Business API path, optional) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""

    # --- WhatsApp (Baileys bridge — QR-pairing path) ---
    # The Node service in apps/whatsapp-bridge owns the actual WA Web sockets.
    # FastAPI talks to it over HTTP for session lifecycle + outbound sends;
    # the bridge POSTs inbound messages back to /webhooks/whatsapp-baileys.
    # Both directions are auth'd by the shared `whatsapp_bridge_secret`.
    whatsapp_bridge_url: str = "http://localhost:8787"
    whatsapp_bridge_secret: str = ""
    whatsapp_bridge_timeout_s: int = 30

    # --- Email ---
    # `console` logs the rendered email to stdout (dev). `smtp` uses the
    # values below. For production use SES, Postmark, or Mailgun via SMTP.
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "Legal AI OS <noreply@example.com>"
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_smtp_use_tls: bool = True
    email_smtp_use_ssl: bool = False

    # --- Observability ---
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1  # 10% of requests traced
    sentry_profiles_sample_rate: float = 0.1
    log_level: str = "INFO"

    # --- Feature flags ---
    enable_whatsapp: bool = True
    enable_whatsapp_baileys: bool = True
    enable_moyasar: bool = True
    # When true, /v1/whatsapp/session/start refuses tenants without an
    # active subscription. Disable for local dev where there's no billing.
    require_subscription_for_whatsapp: bool = True

    # When true (default), the database is expected to have the pgvector
    # extension installed. Set to false to fall back to JSON-stored embeddings
    # with Python-side cosine similarity (slower but works on Windows /
    # managed Postgres instances that lack the extension).
    use_pgvector: bool = True

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
