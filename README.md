# Legal AI OS — Saudi Edition

A production-ready, multi-tenant SaaS platform that gives Saudi law firms an
AI-native operating system: legal research with citations, contract review,
case analysis, document drafting, CRM, WhatsApp client channel, and billing.

> Bilingual (Arabic / English), tenant-isolated, RAG-grounded, and
> deployable on any S3-compatible cloud or on Saudi-resident infrastructure.

---

## Repository layout

```
.
├── apps/
│   ├── api/        # FastAPI backend (Python 3.11)
│   └── web/        # Next.js 14 frontend (App Router, TS)
├── packages/
│   └── shared/     # Shared types, prompts, legal taxonomies
├── infra/
│   ├── docker/     # Dockerfiles + entrypoints
│   └── nginx/      # Reverse proxy config
├── docs/           # Architecture, API, DB, deployment docs
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick start (local development)

Prerequisites: Docker Desktop, Node 20+, Python 3.11+, pnpm 9+.

```bash
cp .env.example .env
docker compose up -d postgres redis minio
cd apps/api && pip install -r requirements.txt && alembic upgrade head && python -m app.cli seed
uvicorn app.main:app --reload --port 8000

# in another terminal
cd apps/web && pnpm install && pnpm dev
```

Visit `http://localhost:3030` (web) and `http://localhost:8000/docs` (API).

---

## What's inside

| Capability             | Where                                                   |
| ---------------------- | ------------------------------------------------------- |
| Multi-tenant data      | `apps/api/app/db/tenancy.py` (row-level + schema-ish)   |
| RAG pipeline           | `apps/api/app/services/rag.py` (+ embeddings, chunking) |
| LLM provider abstract  | `apps/api/app/services/llm.py`                          |
| Contract review        | `apps/api/app/services/contract_analyzer.py`            |
| Case analysis          | `apps/api/app/services/case_analyzer.py`                |
| WhatsApp channel       | `apps/api/app/services/whatsapp.py`                     |
| Stripe + Moyasar       | `apps/api/app/services/billing.py`                      |
| Storage (S3 / MinIO)   | `apps/api/app/services/storage.py`                      |
| Background jobs        | `apps/api/app/workers/`                                 |
| Auth / RBAC            | `apps/api/app/core/security.py`                         |
| i18n (AR/EN, RTL)      | `apps/web/messages/`, `apps/web/src/i18n/`              |
| Marketing pages        | `apps/web/src/app/[locale]/(marketing)/`                |
| Lawyer dashboard       | `apps/web/src/app/[locale]/(dashboard)/`                |
| Admin panel            | `apps/web/src/app/[locale]/(admin)/`                    |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/API.md`](docs/API.md),
[`docs/DATABASE.md`](docs/DATABASE.md) and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## License

Proprietary — all rights reserved. Contact the maintainers for licensing.
