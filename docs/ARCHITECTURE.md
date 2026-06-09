# Architecture — Legal AI OS — Saudi Edition

## 1. High-level diagram

```
                        ┌──────────────────────────────────┐
                        │           Browser (lawyer)        │
                        └──────────────┬───────────────────┘
                                       │ HTTPS
                       ┌───────────────▼────────────────┐
                       │   Next.js 14 (App Router, TS)  │
                       │   - Marketing (i18n AR/EN)     │
                       │   - Lawyer dashboard           │
                       │   - Admin panel                │
                       │   - /api/v1/* proxy w/ cookie  │
                       └───────┬───────────────┬────────┘
                               │               │
                               │ JSON / multipart
                               │               │
            ┌──────────────────▼───────────────▼──────────────────┐
            │                FastAPI (Python 3.11)                 │
            │  Routers: auth, chat, documents, contracts, cases,  │
            │           clients, drafting, templates, plans,       │
            │           subscriptions, admin, webhooks             │
            │  Services: rag, llm, embeddings, document_processor, │
            │            contract_analyzer, case_analyzer,         │
            │            drafting, billing, whatsapp, storage      │
            └────┬───────────────┬────────────────┬─────────────┬──┘
                 │               │                │             │
                 │               │                │             │
        ┌────────▼─────┐  ┌──────▼─────┐  ┌───────▼──────┐  ┌──▼───┐
        │  PostgreSQL  │  │    Redis    │  │   S3 / MinIO │  │ Twilio│
        │  + pgvector  │  │  (Celery,   │  │  (documents) │  │  +    │
        │              │  │   cache)    │  │              │  │Stripe/│
        └──────────────┘  └─────┬───────┘  └──────────────┘  │Moyasar│
                                │                            └───────┘
                          ┌─────▼─────┐
                          │  Celery    │
                          │  workers   │
                          │  ingestion │
                          │  llm       │
                          └────────────┘
                                ▲
                                │  WhatsApp inbound  Twilio webhook
```

## 2. Tenancy model

- A **tenant** is a single law firm.
- Almost every business table carries a non-null `tenant_id` (`TenantMixin` in
  `app/db/base.py`). The schema makes cross-tenant rows physically distinct.
- A platform-owned tenant called `platform` (slug `platform`, seeded by
  `python -m app.cli seed`) holds:
  - global Saudi-law datasets (uploaded by super admins);
  - shared starter templates (NDA, POA, Employment, Demand letter…).
- The retrieval layer fans out to *both* the caller's tenant **and** the
  platform tenant by default, so every firm gets answers grounded in base
  Saudi laws plus their own files.
- Three layers enforce isolation:
  1. Schema (FK + index on `tenant_id`).
  2. `TenantQuery.for_tenant(model, tenant_id)` query helpers.
  3. Service layer always passes `tenant_id` from the JWT-resolved
     `Principal` (`app/core/deps.py`).

## 3. Authentication & RBAC

- Stateless JWT (`HS256`) issued by `app/core/security.py`.
- Token carries: `sub` (user id), `tid` (tenant id), `role`.
- Roles: `super_admin`, `admin`, `lawyer`, `staff`. Enforced by
  `require_role(...)` and `require_super_admin` dependencies.
- Refresh tokens are separate, longer-lived, and only accepted at
  `POST /v1/auth/refresh`.
- Browser session uses **http-only cookies**: `lai_access` / `lai_refresh`.
  Client JS never sees the bearer token; the Next.js `/api/v1/*` proxy
  attaches it server-side.

## 4. RAG pipeline

```
upload  → MinIO/S3
        → Celery (ingestion queue):
              parse PDF/DOCX → tiktoken-aware chunker
                             → batched OpenAI embeddings (3072-d default)
                             → INSERT into document_chunks (with HNSW index)
        → Document.status = INDEXED

ask    → embed query
       → hybrid retrieve (cosine via pgvector + trigram via pg_trgm)
       → re-rank by weighted sum
       → build prompt: system + history + retrieved chunks + question
       → LLM (OpenAI / Anthropic, configurable via env)
       → persist user + assistant messages, citations stamped on the row
```

Citations are stored as JSONB on every assistant `Message` so the UI can
re-render the exact same exchange (with clickable references) without
re-running the model.

## 5. WhatsApp channel

- Inbound flow:
  Twilio → `/webhooks/whatsapp` → resolve tenant → upsert `WhatsAppContact`
  + `Conversation` → run RAG → persist + send via Twilio REST.
- The assistant emits the literal sentinel `[ESCALATE]` when human review is
  needed; we strip it before sending and record a `WhatsAppEscalation` so the
  lawyer sees it in the dashboard.

## 6. Billing

- Plans (Basic / Pro / Enterprise) are rows in the `plans` table.
- Two providers behind one entry point (`services/billing.start_checkout`):
  - **Stripe** for international cards; runs the standard Checkout Session →
    subscription webhooks state machine.
  - **Moyasar** for Saudi-resident customers (Mada, STC Pay, Apple Pay).
    Uses Invoices for the first checkout; recurring billing renews via a
    scheduled job per period.
- `assert_within_limits` enforces monthly caps for `message`, `document_upload`,
  and `contract_review` from the `usage_events` ledger.

## 7. Storage layout

```
s3://legalai-documents/
  tenants/<tenant_id>/documents/<document_id>/<filename>
```

Per-tenant prefix lets us grant scoped IAM for downstream tools (e.g., OCR
or DLP) without exposing other firms' files.

## 8. Observability

- `structlog` JSON logs (request id + tenant id + path) in production.
- Optional Sentry integration via `SENTRY_DSN`.
- `app/services/audit.py` writes append-only `audit_logs` for compliance.

## 9. Internationalization

- `next-intl` with `ar` (default, RTL) and `en` (LTR).
- Messages live in `apps/web/messages/{ar,en}.json`.
- Locale prefix is `as-needed`: `/` is Arabic, `/en` is English.
- Backend prompts have AR/EN variants; the user's `locale` flows through to
  the LLM system prompt for every request.

## 10. Security checklist

- [x] Tenant isolation at schema, query, and service layers.
- [x] Bcrypt-hashed passwords (`passlib`).
- [x] http-only, sameSite=Lax cookies for tokens.
- [x] CORS limited to the configured `app_base_url`.
- [x] Pre-signed S3 URLs (15 min expiry) for downloads.
- [x] Stripe webhook signature verification.
- [x] Audit log for all auth events and admin actions.
- [x] No secrets in client bundle (`.env` server-only, proxy-attached tokens).
