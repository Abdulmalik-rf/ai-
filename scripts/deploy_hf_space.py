"""Deploy the FastAPI backend to a Hugging Face Docker Space.

Assembles a build context (apps/api code + deploy/hf-space/{Dockerfile,
start.sh, README.md}), creates/updates the Space, and uploads it. Secrets
(DATABASE_URL, S3, CODEX_OAUTH_JSON, JWT_SECRET, …) are set separately via
`set_secrets()` once Supabase details are known — never baked into the image.

Usage:
    python scripts/deploy_hf_space.py            # create + push code
    python scripts/deploy_hf_space.py --secrets  # push secrets from a file
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "apps" / "api"
HF_FILES = ROOT / "deploy" / "hf-space"
TOKEN = (API_DIR / ".hf_token").read_text(encoding="utf-8").strip()

OWNER = "abdulmalik1113456789"
SPACE = f"{OWNER}/ai-law-backend"

# Things we never want in the Space image.
EXCLUDE_DIRS = {".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "tests"}
EXCLUDE_FILES = {".env", ".codex_oauth.json", ".gemini_oauth.json", ".hf_token",
                 ".playwright_state.json", "celerybeat-schedule.bak",
                 "celerybeat-schedule.dat", "celerybeat-schedule.dir"}


def _assemble(dest: Path) -> None:
    """Copy apps/api into dest, then overlay the HF-specific files."""
    def _ignore(dir_path: str, names: list[str]) -> set[str]:
        ig: set[str] = set()
        for n in names:
            if n in EXCLUDE_DIRS or n in EXCLUDE_FILES:
                ig.add(n)
            if n.endswith((".pyc", ".log", ".out", ".err")):
                ig.add(n)
        return ig

    shutil.copytree(API_DIR, dest, ignore=_ignore, dirs_exist_ok=True)
    # Overlay HF files (Dockerfile, start.sh, README.md) at the root.
    for f in ("Dockerfile", "start.sh", "README.md"):
        shutil.copy2(HF_FILES / f, dest / f)


def push_code() -> None:
    api = HfApi(token=TOKEN)
    api.create_repo(SPACE, repo_type="space", space_sdk="docker", private=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        ctx = Path(tmp) / "space"
        _assemble(ctx)
        print(f"Assembled build context ({sum(1 for _ in ctx.rglob('*'))} entries). Uploading…")
        api.upload_folder(
            repo_id=SPACE,
            repo_type="space",
            folder_path=str(ctx),
            commit_message="Deploy AI Law backend",
        )
    print(f"OK — pushed to https://huggingface.co/spaces/{SPACE}")
    print("The Space will now build (Docker). Set secrets before it can start serving.")


def set_secrets(secrets_file: Path) -> None:
    """Push KEY=VALUE lines from a file as Space secrets (one per line)."""
    api = HfApi(token=TOKEN)
    n = 0
    for line in secrets_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        api.add_space_secret(repo_id=SPACE, key=k.strip(), value=v.strip())
        n += 1
        print(f"  set secret: {k.strip()}")
    print(f"OK — {n} secrets set. Restart the Space to apply.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secrets", type=str, help="Path to a KEY=VALUE secrets file to push.")
    args = ap.parse_args()
    if args.secrets:
        set_secrets(Path(args.secrets))
    else:
        push_code()
    return 0


if __name__ == "__main__":
    sys.exit(main())
