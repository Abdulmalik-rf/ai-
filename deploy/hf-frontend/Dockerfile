# Hugging Face Space (Docker) — runs the Next.js frontend via `next start`.
# Build happens in the image so container start is fast. The backend URL is
# baked into the app (src/lib/api.ts default), so no runtime env is required.
FROM node:20-slim

ENV NEXT_TELEMETRY_DISABLED=1 \
    PORT=7860 \
    HOSTNAME=0.0.0.0

WORKDIR /app
RUN corepack enable

# Install deps first (layer-cached across source changes).
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# App source + production build.
COPY . ./
RUN pnpm build

# HF Spaces run as UID 1000.
RUN useradd -m -u 1000 user && chown -R user:user /app
USER user

EXPOSE 7860
CMD ["pnpm", "start"]
