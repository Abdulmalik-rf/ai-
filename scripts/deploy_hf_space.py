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

# WHITELIST — only these paths from apps/api go into the Space. Whitelisting
# (not blacklisting) guarantees no stray secret / browser-profile / cache
# file leaks in, no matter what's sitting in apps/api locally.
INCLUDE = ["app", "alembic", "alembic.ini", "requirements.txt"]

# Within the copied trees, still skip caches/compiled junk.
_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _assemble(dest: Path) -> None:
    """Copy ONLY the whitelisted paths, then overlay the HF-specific files."""
    def _ignore(dir_path: str, names: list[str]) -> set[str]:
        return {n for n in names if n in _SKIP_DIRS or n.endswith((".pyc", ".log", ".out", ".err"))}

    dest.mkdir(parents=True, exist_ok=True)
    for rel in INCLUDE:
        src = API_DIR / rel
        if not src.exists():
            raise FileNotFoundError(f"whitelisted path missing: {src}")
        if src.is_dir():
            shutil.copytree(src, dest / rel, ignore=_ignore, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest / rel)

    # Overlay HF files (Dockerfile, start.sh, README.md) at the root.
    for f in ("Dockerfile", "start.sh", "README.md"):
        shutil.copy2(HF_FILES / f, dest / f)

    # Hard safety check: refuse to deploy if any secret-ish file slipped in.
    bad = [p for p in dest.rglob("*") if p.is_file() and (
        p.name in (".env", ".hf_token", ".hf_secrets", ".deploy_secrets",
                   ".codex_oauth.json", ".gemini_oauth.json", ".playwright_state.json")
        or p.name.endswith(("_oauth.json", "_secrets"))
        or ".playwright_userdata" in str(p) or p.name.endswith(".env")
    )]
    if bad:
        raise RuntimeError(f"Refusing to deploy — secret-ish files in context: {[str(b) for b in bad]}")


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
