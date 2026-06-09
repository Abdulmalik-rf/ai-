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
# Build tools in case any approved dependency needs to compile a native addon.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 make g++ && rm -rf /var/lib/apt/lists/*
RUN corepack enable

# Install deps first (layer-cached across source changes).
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --no-frozen-lockfile

# App source + production build.
COPY . ./
RUN pnpm build

# HF Spaces run as UID 1000.
RUN useradd -m -u 1000 user && chown -R user:user /app
USER user

EXPOSE 7860
CMD ["pnpm", "start"]
