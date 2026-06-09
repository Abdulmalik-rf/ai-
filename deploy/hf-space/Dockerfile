# Hugging Face Space (Docker SDK) — self-contained FastAPI ML backend.
# Runs Redis + MinIO inside the container alongside the API, so the only
# external dependency is the Supabase Postgres. The embedding model
# downloads at runtime into HF_HOME (cached on the Space's 50 GB disk).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/hf \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/st

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev poppler-utils curl redis-server \
    && curl -fsSL https://dl.min.io/server/minio/release/linux-amd64/minio -o /usr/local/bin/minio \
    && chmod +x /usr/local/bin/minio \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . ./

# HF Spaces run the container as UID 1000. Make the workdir + data dirs
# writable (model cache, MinIO data, the refreshed OAuth token file).
RUN useradd -m -u 1000 user \
    && mkdir -p /app/.cache /data/minio \
    && chown -R user:user /app /data
USER user

EXPOSE 7860
CMD ["bash", "start.sh"]
