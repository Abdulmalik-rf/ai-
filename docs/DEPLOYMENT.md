# Deployment guide

A practical, step-by-step walkthrough for taking Legal AI OS from a fresh
git clone to a public production deployment.

## 1. Local development

```bash
git clone <repo>
cd "AI Law"
cp .env.example .env

# Bring up infra (Postgres + pgvector, Redis, MinIO)
docker compose up -d postgres redis minio

# Backend
cd apps/api
python -m venv .venv && source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\Activate.ps1                         # Windows PowerShell
pip install -r requirements.txt
alembic upgrade head
python -m app.cli seed
python -m app.cli create-superadmin admin@example.com  # prompts for password
uvicorn app.main:app --reload --port 8000

# In another terminal — Celery worker
celery -A app.workers.celery_app worker -l info -Q default,ingestion,llm

# Frontend
cd ../web
pnpm install
pnpm dev
```

Visit:
- `http://localhost:3030` — marketing + dashboard
- `http://localhost:8000/docs` — Swagger UI
- `http://localhost:9001` — MinIO console (login `minioadmin / minioadmin`)

## 2. Configure provider keys

Edit `.env` (never commit) with real values for the providers you intend to
use:

| Provider  | Variables                                                            |
| --------- | -------------------------------------------------------------------- |
| OpenAI    | `LLM_API_KEY`, `LLM_MODEL`, `EMBEDDINGS_MODEL`                       |
| Anthropic | switch `LLM_PROVIDER=anthropic`, set `LLM_MODEL=claude-...`, `LLM_API_KEY` |
| Stripe    | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*`       |
| Moyasar   | `MOYASAR_SECRET_KEY`, `MOYASAR_PUBLISHABLE_KEY`, `MOYASAR_WEBHOOK_SECRET` |
| Twilio    | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`    |

After changing `STRIPE_PRICE_*`, re-run the platform seed or manually update
the `plans.stripe_price_id` rows.

## 3. Production options

### 3a. Single VPS (simplest)

Tested target: an Ubuntu 22.04 VM with 4 vCPU / 8 GB RAM. Suitable for early-
stage firms.

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
# Clone
git clone <repo> && cd "AI Law"
# Production env
cp .env.example .env
# Edit .env: set APP_ENV=production, real secrets, your domain.
docker compose -f docker-compose.yml up -d --build
```

Add an Nginx reverse proxy (sample at `infra/nginx/nginx.conf`) with TLS
via Let's Encrypt:

```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d app.your-domain.sa
```

### 3b. Managed cloud (recommended for scale)

| Component           | Suggested provider                             |
| ------------------- | ---------------------------------------------- |
| API + workers       | AWS ECS Fargate / GCP Cloud Run / Fly.io       |
| Postgres + pgvector | AWS RDS Postgres 16 (or Supabase / Neon)       |
| Redis               | AWS ElastiCache / Upstash                      |
| Object storage      | AWS S3 with bucket `legalai-documents`         |
| Frontend            | Vercel (Next.js standalone) / Cloudflare Pages |
| DNS / TLS           | Cloudflare                                     |

#### Saudi data residency

Some clients need data inside KSA. Use:

- AWS Middle East (Bahrain) — `me-south-1`
- Google Cloud Saudi Arabia — `me-central2` (Dammam)
- Local providers (e.g., NourNet, STC Cloud)

Set `S3_REGION` and `S3_ENDPOINT_URL` accordingly. `pgvector` works on any
Postgres 14+; ensure your managed offering allows extension creation.

## 4. Post-deploy steps

1. `alembic upgrade head` (run once via a one-off task).
2. `python -m app.cli seed` (idempotent; safe to re-run).
3. `python -m app.cli create-superadmin you@firm.sa`.
4. Sign in to `/admin` and upload your base Saudi-law datasets:
   - Companies Law (Royal Decree M/3)
   - Labor Law (Royal Decree M/51)
   - Civil Transactions Law
   - Anti-Commercial Fraud Law
   - Government Tenders & Procurement Law
   - … any others relevant to your firm's specialties.
5. In Stripe / Moyasar, create the products + recurring prices for each
   plan and paste the IDs into `plans` rows or env (then re-seed).
6. In Twilio, configure the WhatsApp inbound webhook to
   `https://your-domain/webhooks/whatsapp`.
7. In Stripe and Moyasar, configure outbound webhooks to
   `https://your-domain/webhooks/stripe` and `/webhooks/moyasar`.

## 5. Operations

- **Logs**: structured JSON to stdout; ship to CloudWatch / Loki / Datadog.
- **Metrics**: API exposes a `/health` endpoint; add Prometheus exporters
  per service if needed.
- **Backups**: take nightly Postgres snapshots and S3 versioning.
- **Migrations**: every release runs `alembic upgrade head` as a pre-deploy
  hook.
- **Workers**: scale `worker` replicas independently of the API. Each queue
  (`default`, `ingestion`, `llm`) can run on different instance sizes.

## 6. Smoke test

```bash
# 1. Sign up
curl -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"firm_name":"Demo","full_name":"You","email":"you@demo.sa","password":"a-strong-pass","locale":"ar"}'

# 2. Ask a question (use the access_token from above)
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message":"ما هي مدة فترة التجربة في نظام العمل السعودي؟","locale":"ar"}'
```

You should get back a JSON response with `message.content` and at least one
citation if the platform Saudi-law datasets have been ingested.
