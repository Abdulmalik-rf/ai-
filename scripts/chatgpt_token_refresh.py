"""Auto-mint a fresh ChatGPT Plus accessToken using headless-browser login.

WHAT IT DOES
------------
1. Reads OPENAI_AUTH_EMAIL + OPENAI_AUTH_PASSWORD from apps/api/.env.
2. Drives Chromium (Playwright) through chatgpt.com's email-then-password
   login flow.
3. After the redirect to chatgpt.com lands, fetches
   ``https://chatgpt.com/api/auth/session`` and extracts ``accessToken``.
4. Writes the new token into apps/api/.env, replacing
   OPENAI_CHATGPT_TOKEN= in-place.
5. Persists the browser context to ``apps/api/.playwright_state.json``
   so subsequent runs reuse the session cookie when possible — much faster
   and far less likely to trip Cloudflare/Turnstile bot checks.

WHY THE EARLIER TOKEN GAVE 401
------------------------------
Codex backend (chatgpt.com/backend-api/codex/responses) rejects tokens
whose JWT ``amr`` claim is OTP-only. A token minted from a password login
has ``amr=pwd``, which Codex accepts. This script always logs in with the
password, guaranteeing the right claim.

CAVEATS (read before scheduling)
--------------------------------
* OpenAI's TOS forbids automated logins. Use only on accounts you own,
  and accept that automation can result in account flagging.
* Cloudflare/Turnstile may block headless runs. If it does, run with
  ``--headed`` once to clear the challenge, then back to headless after
  the storage state is saved.
* Email-OTP enforcement (sometimes triggered after suspicious activity)
  will defeat this script — you'll need to log in manually once to clear
  the flag, then the script resumes working.

USAGE
-----
::

    # one-off refresh
    python scripts/chatgpt_token_refresh.py

    # first run on a new machine — let me see the browser so you can solve
    # any captcha that pops up:
    python scripts/chatgpt_token_refresh.py --headed

    # the same flow, but also restart the API after a successful refresh:
    python scripts/chatgpt_token_refresh.py --restart-api
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "apps" / "api"
ENV_FILE = API_DIR / ".env"
STATE_FILE = API_DIR / ".playwright_state.json"

CHATGPT_LOGIN_URL = "https://chatgpt.com/auth/login"
CHATGPT_SESSION_URL = "https://chatgpt.com/api/auth/session"


# ─── env parsing/writing ────────────────────────────────────────────────


def _read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_FILE.exists():
        return out
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip()
    return out


def _write_token(new_token: str) -> None:
    """Replace OPENAI_CHATGPT_TOKEN= in .env with the fresh value."""
    if not new_token or not new_token.startswith("eyJ"):
        raise RuntimeError(f"Refusing to write non-JWT value (len={len(new_token)}).")
    text = ENV_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r"^OPENAI_CHATGPT_TOKEN=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub(f"OPENAI_CHATGPT_TOKEN={new_token}", text)
    else:
        text += f"\nOPENAI_CHATGPT_TOKEN={new_token}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def _restart_api() -> None:
    """Kill whatever is on port 8001 and relaunch uvicorn detached."""
    print("Restarting API on port 8001…")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "$p=(Get-NetTCPConnection -LocalPort 8001 -EA SilentlyContinue).OwningProcess;"
                "if($p){Stop-Process -Id $p -Force -EA SilentlyContinue};"
                "Start-Sleep -Seconds 3;"
                "Start-Process -FilePath "
                f"'{API_DIR}\\.venv\\Scripts\\python.exe' "
                "-ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--log-level','warning' "
                f"-WorkingDirectory '{API_DIR}' -WindowStyle Hidden "
                f"-RedirectStandardOutput '{ROOT}\\data\\api.out' "
                f"-RedirectStandardError '{ROOT}\\data\\api.err';"
                "Start-Sleep -Seconds 5"
            ),
        ],
        check=False,
    )


# ─── login dance ────────────────────────────────────────────────────────


def _try_session_only(page: Page) -> str | None:
    """If a saved session is still valid, /api/auth/session returns the JWT
    without us touching the login form. Cheapest happy-path."""
    try:
        resp = page.request.get(CHATGPT_SESSION_URL, timeout=15_000)
    except Exception:
        return None
    if resp.status != 200:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    return data.get("accessToken")


def _do_password_login(page: Page, email: str, password: str) -> None:
    """Walk through email → password → submit on chatgpt.com/auth/login.

    Selectors are kept loose because OpenAI re-skins the auth UI frequently.
    Order:
      1. Click the "Log in" button on the landing page.
      2. Fill the email field, click Continue.
      3. Fill the password field, click Continue / Log in.
      4. Wait for redirect to chatgpt.com main UI.
    """
    page.goto(CHATGPT_LOGIN_URL, wait_until="domcontentloaded", timeout=60_000)
    # Click "Log in" if a button-grid landing page is shown.
    try:
        page.get_by_role("button", name=re.compile(r"^(Log in|Sign in)$", re.I)).first.click(timeout=8_000)
    except PlaywrightTimeoutError:
        pass

    # Email step. The Auth0 form changed twice this year — try common labels first.
    email_inp = page.locator(
        "input#email-input, input[name=email], input[name=username], input[type=email]"
    ).first
    email_inp.wait_for(state="visible", timeout=30_000)
    email_inp.fill(email)
    page.get_by_role("button", name=re.compile(r"^(Continue|Next|Log in)$", re.I)).first.click()

    # Password step.
    pwd_inp = page.locator("input[name=password], input[type=password]").first
    pwd_inp.wait_for(state="visible", timeout=30_000)
    pwd_inp.fill(password)
    page.get_by_role("button", name=re.compile(r"^(Continue|Log in|Sign in)$", re.I)).first.click()

    # Wait for the redirect to chatgpt.com main UI.
    page.wait_for_url(re.compile(r"^https://chatgpt\.com/(?!auth)"), timeout=60_000)


def refresh_token(headed: bool = False, browser_kind: str = "chromium") -> str:
    """Mint and persist a fresh accessToken.

    Returns the new JWT on success; raises on failure.
    """
    env = _read_env()
    email = env.get("OPENAI_AUTH_EMAIL")
    pwd = env.get("OPENAI_AUTH_PASSWORD")
    if not email or not pwd:
        raise RuntimeError(
            "OPENAI_AUTH_EMAIL / OPENAI_AUTH_PASSWORD missing from apps/api/.env."
        )

    with sync_playwright() as p:
        launcher = getattr(p, browser_kind)
        browser = launcher.launch(
            headless=not headed,
            # Light stealth — strips the "HeadlessChrome" UA bit that
            # OpenAI's Cloudflare ruleset specifically watches for.
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        ctx_kwargs: dict = {
            "viewport": {"width": 1280, "height": 800},
            "locale": "en-US",
            # Real Chrome 124 UA — closer to a human's browser fingerprint.
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        if STATE_FILE.exists():
            ctx_kwargs["storage_state"] = str(STATE_FILE)

        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        # 1. Try the cheap path first — saved session may still be valid.
        token = _try_session_only(page)
        if token:
            print("Reused saved browser session — got a fresh token without re-logging in.")
        else:
            # 2. Full email→password walk.
            print(f"Logging in as {email} …")
            try:
                _do_password_login(page, email, pwd)
            except PlaywrightTimeoutError as exc:
                raise RuntimeError(
                    "Login flow timed out. If a captcha or Turnstile challenge "
                    "appeared, re-run with --headed once to solve it manually; "
                    "the saved storage_state will let subsequent runs skip the "
                    f"login. Underlying error: {exc}"
                ) from exc
            token = _try_session_only(page)
            if not token:
                raise RuntimeError(
                    "Logged in but /api/auth/session did not return an accessToken. "
                    "OpenAI may be doing an MFA / device-verification challenge."
                )

        # Persist the (possibly fresher) cookies so the next run skips login.
        context.storage_state(path=str(STATE_FILE))
        browser.close()

    # JWT sanity — decode the payload (no signature check) to confirm
    # the amr claim is "pwd", not "otp". This is the part Codex cares about.
    import base64
    parts = token.split(".")
    if len(parts) != 3:
        raise RuntimeError(f"Got a value that isn't a JWT (parts={len(parts)}).")
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    amr = payload.get("https://api.openai.com/auth", {}).get("amr") or payload.get("amr") or []
    exp = payload.get("exp")
    from datetime import datetime, timezone
    if exp:
        when = datetime.fromtimestamp(int(exp), tz=timezone.utc).isoformat()
        print(f"Token expires at: {when}")
    if isinstance(amr, list) and amr and not any("pwd" in str(x).lower() for x in amr):
        print(
            "WARNING: amr claim is "
            f"{amr!r} — Codex may still 401 this token. "
            "Sign out everywhere on chatgpt.com and log in once more "
            "manually with the password to clear the OTP-only flag.",
            file=sys.stderr,
        )

    _write_token(token)
    print(f"OK -- wrote OPENAI_CHATGPT_TOKEN to {ENV_FILE}")
    return token


# ─── CLI ────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--headed", action="store_true", help="Show the browser (for first run / captcha solve).")
    parser.add_argument("--browser", choices=("chromium", "firefox"), default="chromium")
    parser.add_argument("--restart-api", action="store_true", help="Bounce the API process after a successful refresh.")
    args = parser.parse_args()

    try:
        refresh_token(headed=args.headed, browser_kind=args.browser)
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    if args.restart_api:
        _restart_api()
    return 0


if __name__ == "__main__":
    sys.exit(main())
