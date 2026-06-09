# Database schema

PostgreSQL 16 with three extensions:

- `vector`     — pgvector for embeddings (HNSW index, cosine distance)
- `pg_trgm`    — trigram similarity for keyword recall
- `unaccent`   — diacritic-insensitive search (relevant for Arabic)

All tables have `id UUID PK`, `created_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ`.
Tenant-scoped tables also have `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`.

## Core tables

### tenants
| column                | type         | notes                                  |
| --------------------- | ------------ | -------------------------------------- |
| name                  | varchar(200) |                                        |
| slug                  | varchar(80)  | unique, used in URLs                   |
| country               | varchar(2)   | default `SA`                           |
| default_locale        | varchar(8)   | `ar` / `en`                            |
| is_active             | boolean      | suspend toggle                         |
| stripe_customer_id    | varchar(64)  | nullable                               |
| moyasar_customer_id   | varchar(64)  | nullable                               |

### users
| column             | type         | notes                              |
| ------------------ | ------------ | ---------------------------------- |
| tenant_id          | UUID         | nullable for `super_admin`         |
| email              | varchar(255) | unique                             |
| full_name          | varchar(200) |                                    |
| hashed_password    | varchar(255) | bcrypt                             |
| role               | varchar(32)  | `admin` / `lawyer` / `staff` / `super_admin` |
| locale             | varchar(8)   |                                    |
| is_active          | boolean      |                                    |
| is_email_verified  | boolean      |                                    |

### clients (CRM)
`name`, `kind`, `national_id`, `cr_number`, `email`, `phone`, `address`,
`notes`, `tags JSONB[]`.

### cases
`reference`, `title`, `description`, `domain`, `status`, `client_id`,
`assigned_lawyer_id`, `ai_analysis JSONB` (cached LLM output).

`domain` ∈ {commercial, labor, family, criminal, real_estate, administrative, ip, corporate, banking, other}.
`status` ∈ {intake, open, in_court, settled, closed, archived}.

### documents
`title`, `source` (upload | global | generated), `status`,
`storage_key`, `mime_type`, `byte_size`, `page_count`, `language`,
`extra_metadata JSONB`, `case_id`.

### document_chunks
The core RAG table.

| column        | type           | notes                              |
| ------------- | -------------- | ---------------------------------- |
| document_id   | UUID           | FK                                 |
| chunk_index   | integer        | 0-based order within the document  |
| page_number   | integer        | nullable                           |
| content       | text           | raw text                           |
| token_count   | integer        | cl100k tokens                      |
| embedding     | vector(N)      | dimension = `EMBEDDINGS_DIM` env   |
| extra_metadata| JSONB          |                                    |

Indexes:
- `ix_document_chunks_embedding_hnsw` — `USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`
- `ix_document_chunks_content_trgm`   — `USING gin (content gin_trgm_ops)`
- `ix_document_chunks_tenant_id` / `ix_document_chunks_document_id`

### conversations / messages
A conversation belongs to a tenant and may also be linked to a `user`,
`client`, or `case`. Each message stores `role`, `content`, `citations JSONB`,
`token_count`, `model`, `latency_ms`.

### plans / subscriptions / usage_events
- `plans`: tier (`basic`/`pro`/`enterprise`), prices in SAR + USD, monthly
  caps, seat limit, Stripe and Moyasar identifiers, `is_active`.
- `subscriptions`: 1-per-tenant, `status` ∈ {trialing, active, past_due,
  canceled, paused}, `provider` ∈ {stripe, moyasar}, period bounds.
- `usage_events`: append-only ledger; aggregated for limit enforcement and
  billing.

### templates
Tenant-scoped or platform-global drafting templates (`is_global=true`).
Bilingual: `title_en`/`title_ar`, `body_en`/`body_ar`, `variables JSONB`.

### whatsapp_contacts / whatsapp_escalations
Maps a phone number to a tenant and (optionally) a CRM client. Escalations
are flagged conversations the lawyer should review.

### audit_logs
Append-only. `action` is a dotted name (`auth.login`, `document.upload`, …),
`actor_user_id`, `target_type`, `target_id`, `ip_address`, `user_agent`,
`extra_metadata JSONB`.

## Migrations

```
cd apps/api
alembic upgrade head     # apply
alembic revision --autogenerate -m "..."  # add a new migration
alembic downgrade -1     # roll back
```
