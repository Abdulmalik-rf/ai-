# Hugging Face Space (Docker SDK) — runs the FastAPI ML backend.
# HF Spaces expects the app to listen on the port declared in README's
# `app_port`. We use 7860 (the HF default). The embedding model downloads
# at runtime into HF_HOME (cached on the Space's 50 GB disk).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/hf \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/st

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev poppler-utils curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (layer-cached across code changes).
COPY requirements.txt ./
RUN pip install -r requirements.txt

# App code (assembled from apps/api by scripts/deploy_hf_space.py).
COPY . ./

# HF Spaces run the container as UID 1000; make the workdir writable so the
# model cache + the refreshed OAuth token file can be written.
RUN useradd -m -u 1000 user && mkdir -p /app/.cache && chown -R user:user /app
USER user

EXPOSE 7860
CMD ["bash", "start.sh"]
