# API reference

Base URL: `http://localhost:8000` (dev).
All v1 endpoints are mounted under `/v1`. Webhooks live at `/webhooks/*`.

Auth: `Authorization: Bearer <access_token>` for everything except `/v1/auth/*`,
`/v1/plans`, and webhook endpoints.

OpenAPI / Swagger UI: `GET /docs` · ReDoc: `GET /redoc` · JSON: `GET /openapi.json`.

---

## Auth — `/v1/auth`

| Method | Path                | Body / Auth                            | Response          |
| ------ | ------------------- | -------------------------------------- | ----------------- |
| POST   | `/v1/auth/signup`   | `{firm_name,full_name,email,password,locale}` | `TokenPair` |
| POST   | `/v1/auth/login`    | `{email,password}`                     | `TokenPair`       |
| POST   | `/v1/auth/refresh`  | `{refresh_token}`                      | `TokenPair`       |
| GET    | `/v1/auth/me`       | bearer                                 | `User`            |

`signup` creates a new tenant + first admin user atomically.

## Chat — `/v1/chat`

| Method | Path                                            | Body / Auth                       |
| ------ | ----------------------------------------------- | --------------------------------- |
| GET    | `/v1/chat/conversations`                        | bearer                            |
| GET    | `/v1/chat/conversations/{id}/messages`          | bearer                            |
| POST   | `/v1/chat`                                      | `{conversation_id?, case_id?, message, locale}` |
| DELETE | `/v1/chat/conversations/{id}`                   | bearer                            |

`POST /v1/chat` runs the full RAG pipeline. Returns the assistant's
message with `citations` populated.

## Documents — `/v1/documents`

| Method | Path                              | Notes                           |
| ------ | --------------------------------- | ------------------------------- |
| POST   | `/v1/documents`                   | `multipart/form-data` with `file`, optional `case_id`, `language`. Returns 202 + Celery task id. |
| GET    | `/v1/documents`                   |                                 |
| GET    | `/v1/documents/{id}`              |                                 |
| GET    | `/v1/documents/{id}/download-url` | 15-minute presigned URL         |
| DELETE | `/v1/documents/{id}`              |                                 |

Allowed MIME types: PDF, DOCX, MS Word, plain text. Max 50 MB.

## Contracts — `/v1/contracts`

| Method | Path                       | Body                                   |
| ------ | -------------------------- | -------------------------------------- |
| POST   | `/v1/contracts/review`     | `{document_id, locale, async_mode?}`   |

Returns `ContractReviewResponse` with `summary`, `findings[]`,
`suggestions[]`, `missing_clauses[]`, `risk_score (0-100)`.

## Cases — `/v1/cases`

| Method | Path                             | Body                       |
| ------ | -------------------------------- | -------------------------- |
| GET    | `/v1/cases`                      |                            |
| POST   | `/v1/cases`                      | `CaseCreate`               |
| GET    | `/v1/cases/{id}`                 |                            |
| PATCH  | `/v1/cases/{id}`                 | `CaseUpdate`               |
| DELETE | `/v1/cases/{id}`                 |                            |
| POST   | `/v1/cases/{id}/analyze`         | `{locale}` → `CaseAnalysisResponse` |

## Clients — `/v1/clients`

Standard CRUD with `ClientCreate` / `ClientUpdate` / `ClientRead`.

## Drafting — `/v1/drafting`

| Method | Path             | Body                                                        |
| ------ | ---------------- | ----------------------------------------------------------- |
| POST   | `/v1/drafting`   | `{template_id?, kind, locale, variables, instructions?}`    |

Returns `{title, body, document_id}`. The generated document is also saved
as a `Document` row of source `generated`.

## Templates — `/v1/templates`

| Method | Path                       | Notes                                       |
| ------ | -------------------------- | ------------------------------------------- |
| GET    | `/v1/templates`            | combines tenant + platform-global templates |
| GET    | `/v1/templates/{id}`       |                                             |

## Plans / Subscriptions

| Method | Path                                | Auth                  |
| ------ | ----------------------------------- | --------------------- |
| GET    | `/v1/plans`                         | public                |
| GET    | `/v1/subscriptions/me`              | bearer                |
| POST   | `/v1/subscriptions/checkout`        | bearer (admin role)   |
| POST   | `/v1/subscriptions/cancel`          | bearer (admin role)   |

`POST /v1/subscriptions/checkout` body:
```
{ plan_tier: "basic" | "pro" | "enterprise",
  provider: "stripe" | "moyasar",
  success_url: "...", cancel_url: "..." }
```

## Admin (super_admin only)

| Method | Path                                  | Notes                                |
| ------ | ------------------------------------- | ------------------------------------ |
| GET    | `/v1/admin/tenants`                   |                                      |
| POST   | `/v1/admin/tenants/{id}/suspend`      |                                      |
| POST   | `/v1/admin/tenants/{id}/activate`     |                                      |
| POST   | `/v1/admin/datasets`                  | upload base Saudi-law document       |
| GET    | `/v1/admin/metrics`                   | platform-wide rollups                |

## Webhooks

| Path                  | Provider                  |
| --------------------- | ------------------------- |
| `/webhooks/stripe`    | Stripe (Stripe-Signature) |
| `/webhooks/moyasar`   | Moyasar                   |
| `/webhooks/whatsapp`  | Twilio (form-encoded)     |

## Errors

All errors return:
```json
{ "detail": "<human-readable message>", "request_id": "..." }
```
- 401 — missing/expired bearer token
- 402 — plan limit reached
- 403 — role / tenant mismatch
- 404 — not found within tenant scope
- 413 / 415 — file too large / unsupported MIME
- 5xx — server error (logged with request id)
