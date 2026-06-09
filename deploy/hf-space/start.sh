#!/usr/bin/env bash
# HF Space entrypoint. Starts in-container Redis + MinIO, reconstructs the
# Codex OAuth creds from a secret, then launches the API on port 7860.
set -e

# --- in-container Redis ---
redis-server --daemonize yes --bind 127.0.0.1 --save "" --appendonly no
echo "start.sh: redis up on 127.0.0.1:6379"

# --- in-container MinIO (S3) ---
export MINIO_ROOT_USER="${S3_ACCESS_KEY:-minioadmin}"
export MINIO_ROOT_PASSWORD="${S3_SECRET_KEY:-minioadmin}"
minio server /data/minio --address ":9000" --console-address ":9001" >/tmp/minio.log 2>&1 &
echo "start.sh: minio starting on :9000"

# --- Codex OAuth creds from the Space secret (ephemeral disk resets) ---
if [ -n "$CODEX_OAUTH_JSON" ]; then
  printf '%s' "$CODEX_OAUTH_JSON" > /app/.codex_oauth.json
  echo "start.sh: wrote .codex_oauth.json from secret"
fi

# Give MinIO a moment, then create the bucket (ignore if it exists).
sleep 3
python - <<'PY' || echo "start.sh: bucket init skipped"
import os, boto3
from botocore.client import Config
s3 = boto3.client(
    "s3", endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000"),
    aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
    aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    region_name=os.environ.get("S3_REGION", "us-east-1"), config=Config(s3={"addressing_style": "path"}),
)
b = os.environ.get("S3_BUCKET", "legalai-documents")
try:
    s3.create_bucket(Bucket=b)
    print("created bucket", b)
except Exception as e:
    print("bucket:", e)
PY

# Schema is migrated from the operator's machine before deploy; re-run here
# as a safety net (non-fatal if already current).
python -m alembic upgrade head || echo "start.sh: alembic upgrade skipped/failed (continuing)"

exec uvicorn app.main:app --host 0.0.0.0 --port 7860
