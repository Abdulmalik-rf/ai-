---
title: AI Law Backend
emoji: ⚖️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Legal AI OS — Saudi Edition backend (FastAPI + RAG)
---

# AI Law Backend

FastAPI backend for the Legal AI OS — Saudi Edition. RAG over a Saudi-law
corpus, multi-advisor case/consultation/contract analysis, and the WhatsApp
agent. The database (Postgres + pgvector) and object storage are external
(Supabase); the LLM brain is ChatGPT gpt-5.5 via Codex OAuth.

Configured entirely through Space **Secrets** (DATABASE_URL, S3 creds,
CODEX_OAUTH_JSON, JWT_SECRET, etc.) — see `deploy/hf-space/` in the source
repo. Not meant to be browsed directly; the Next.js frontend talks to it.
