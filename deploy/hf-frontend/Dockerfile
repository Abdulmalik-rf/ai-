# Hugging Face Space (Docker) — runs the Next.js frontend via `next start`.
# Build happens in the image so container start is fast. The backend URL is
# baked into the app (src/lib/api.ts default), so no runtime env is required.
# Node 22: modern pnpm (11.x) requires the built-in `node:sqlite` module,
# which only exists on Node 22+.
FROM node:22-slim

ENV NEXT_TELEMETRY_DISABLED=1 \
    PORT=7860 \
    HOSTNAME=0.0.0.0

WORKDIR /app
# Build tools in case any dependency needs to compile a native addon.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 make g++ && rm -rf /var/lib/apt/lists/*
# Pin pnpm 9 — pnpm 10+ gates dependency build scripts behind an interactive
# "approve-builds" step (ERR_PNPM_IGNORED_BUILDS) that fails non-interactive
# Docker builds, and it no longer reads package.json's `pnpm` field. pnpm 9
# runs build scripts directly.
RUN npm install -g pnpm@9

# Install deps first (layer-cached across source changes).
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --no-frozen-lockfile

# App source + production build.
COPY . ./
RUN pnpm build

# HF Spaces run as UID 1000 — the node:22 image already provides the `node`
# user at UID 1000, so reuse it (creating another at 1000 collides).
RUN chown -R node:node /app
USER node

EXPOSE 7860
CMD ["pnpm", "start"]
