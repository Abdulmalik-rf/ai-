#!/usr/bin/env bash
# HF Space entrypoint: reconstruct the Codex OAuth creds from the Space
# secret (ephemeral disk resets on restart), then launch the API on 7860.
set -e

if [ -n "$CODEX_OAUTH_JSON" ]; then
  printf '%s' "$CODEX_OAUTH_JSON" > /app/.codex_oauth.json
  echo "start.sh: wrote .codex_oauth.json from secret"
fi

# DB schema is migrated from the operator's machine against Supabase before
# first deploy; run it here too in case the Space is the first to touch a
# fresh DB. Non-fatal if already up to date.
python -m alembic upgrade head || echo "start.sh: alembic upgrade skipped/failed (continuing)"

exec uvicorn app.main:app --host 0.0.0.0 --port 7860
