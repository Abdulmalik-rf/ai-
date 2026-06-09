---
title: AI Law Frontend
emoji: ⚖️
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Legal AI OS — Saudi Edition dashboard (Next.js)
---

# AI Law Frontend

Next.js dashboard for the Legal AI OS — Saudi Edition. Talks to the FastAPI
backend Space; the backend URL is baked into `src/lib/api.ts`. Auth, the
secure API proxy, and server rendering all run here via `next start`.
