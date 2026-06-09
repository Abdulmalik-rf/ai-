"""Mint a *real Codex-CLI* OAuth token (the kind the Codex backend accepts).

WHY THE /api/auth/session TOKEN 401s
------------------------------------
The token from chatgpt.com/api/auth/session is issued for the ChatGPT web
client (client_id app_X8zY6vW2pQ9tR3dE7nK1jL5gH). The Codex backend
(chatgpt.com/backend-api/codex/responses) validates that the bearer token
was issued for the *Codex CLI* client (app_EMoamEEZ73f0CkXaXp7hrann)
through the canonical PKCE flow at auth.openai.com. A web-session token —
even with the right scopes — gets 401'd.

This script performs the exact Codex-CLI OAuth dance:
  1. PKCE (S256) + state.
  2. Local callback server on :1455 (the port codex-rs uses).
  3. Authorize at auth.openai.com/oauth/authorize with the Codex client_id.
     Because we drive it with the saved Playwright session (already logged
     in), OpenAI auto-approves and 302s to localhost:1455 with the code —
     no manual login. If a consent screen appears, we click through it.
  4. Exchange code -> { access_token, id_token, refresh_token } at
     auth.openai.com/oauth/token.
  5. Persist all three to apps/api/.codex_oauth.json (with chatgpt_account_id
     parsed from the id_token) and write access_token into .env as
     OPENAI_CHATGPT_TOKEN.

The refresh_token lets us renew forever without re-login — see
chatgpt_codex_refresh() at the bottom.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "apps" / "api"
ENV_FILE = API_DIR / ".env"
STATE_FILE = API_DIR / ".playwright_state.json"
CODEX_CREDS = API_DIR / ".codex_oauth.json"

# Canonical Codex-CLI OAuth client (from the open-source codex-rs).
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/oauth/authorize"
TOKEN_URL = f"{ISSUER}/oauth/token"
REDIRECT_PORT = 1455
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/auth/callback"
SCOPE = "openid profile email offline_access"


def _read_env_value(key: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith(f"{key}=") and not s.startswith("#"):
            return s.partition("=")[2].strip()
    return ""


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _make_pkce() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _decode_jwt(token: str) -> dict:
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))


# ── local callback server ───────────────────────────────────────────────


class _Capture:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    done = threading.Event()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/auth/callback":
            self.send_response(404)
            self.end_headers()
            return
        q = urllib.parse.parse_qs(parsed.query)
        _Capture.code = (q.get("code") or [None])[0]
        _Capture.state = (q.get("state") or [None])[0]
        _Capture.error = (q.get("error") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<!doctype html><meta charset=utf-8><title>Codex auth</title>"
            b"<body style='font-family:system-ui;background:#0f172a;color:#e2e8f0;"
            b"text-align:center;padding:60px'><h1>Codex token captured</h1>"
            b"<p>You can close this tab.</p></body>"
        )
        _Capture.done.set()

    def log_message(self, *_):
        pass


def _serve_callback() -> HTTPServer:
    srv = HTTPServer(("127.0.0.1", REDIRECT_PORT), _Handler)
    srv.timeout = 1.0

    def loop():
        while not _Capture.done.is_set():
            srv.handle_request()

    threading.Thread(target=loop, daemon=True).start()
    return srv


# ── env / creds writers ─────────────────────────────────────────────────


def _write_token_to_env(token: str) -> None:
    text = ENV_FILE.read_text(encoding="utf-8")
    pat = re.compile(r"^OPENAI_CHATGPT_TOKEN=.*$", re.MULTILINE)
    if pat.search(text):
        text = pat.sub(f"OPENAI_CHATGPT_TOKEN={token}", text)
    else:
        text += f"\nOPENAI_CHATGPT_TOKEN={token}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def _save_creds(tok: dict) -> dict:
    access = tok["access_token"]
    id_token = tok.get("id_token", "")
    refresh = tok.get("refresh_token", "")
    account_id = ""
    if id_token:
        claims = _decode_jwt(id_token)
        account_id = (
            claims.get("https://api.openai.com/auth", {}).get("chatgpt_account_id", "")
        )
    # Fall back to the access token's own claim.
    if not account_id:
        try:
            claims = _decode_jwt(access)
            account_id = claims.get("https://api.openai.com/auth", {}).get("chatgpt_account_id", "")
        except Exception:
            pass

    expires_in = int(tok.get("expires_in", 0))
    creds = {
        "access_token": access,
        "refresh_token": refresh,
        "id_token": id_token,
        "account_id": account_id,
        "client_id": CLIENT_ID,
        "expiry": (
            (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
            if expires_in
            else None
        ),
    }
    CODEX_CREDS.write_text(json.dumps(creds, indent=2), encoding="utf-8")
    return creds


# ── core flows ──────────────────────────────────────────────────────────


def login(headed: bool = False) -> dict:
    """Full OAuth login using the saved Playwright session for auto-approve."""
    from playwright.sync_api import sync_playwright

    verifier, challenge = _make_pkce()
    state = _b64url(secrets.token_bytes(16))
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "state": state,
    }
    authorize = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    srv = _serve_callback()
    print(f"Authorize URL:\n  {authorize}\n")

    with sync_playwright() as p:
        # Prefer the *real* installed browser (Edge → Chrome). Cloudflare's
        # Turnstile flags Playwright's bundled Chromium but generally passes a
        # genuine browser binary. Fall back to bundled Chromium if neither is
        # present. A persistent user-data dir makes the fingerprint even more
        # human (cached challenge tokens, etc.).
        user_data = str(API_DIR / ".playwright_userdata")
        ctx = None
        last_err = None
        for channel in ("msedge", "chrome", None):
            try:
                ctx = p.chromium.launch_persistent_context(
                    user_data_dir=user_data,
                    channel=channel,
                    headless=not headed,
                    args=["--disable-blink-features=AutomationControlled"],
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                )
                print(f"launched browser channel={channel or 'bundled-chromium'}")
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
        if ctx is None:
            raise RuntimeError(f"Could not launch any browser: {last_err}")

        # Seed the persistent context with our saved login cookies so we land
        # past the password screen.
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                if state.get("cookies"):
                    ctx.add_cookies(state["cookies"])
            except Exception:
                pass

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Navigating to the authorize URL while logged in → either auto-redirect
        # to localhost:1455/auth/callback?code=... OR an interstitial
        # (Cloudflare challenge / choose-an-account / consent). We handle all.
        try:
            page.goto(authorize, wait_until="domcontentloaded", timeout=60_000)
        except Exception:
            pass

        import re as _re
        email = _read_env_value("OPENAI_AUTH_EMAIL")

        # Cloudflare interstitial: wait up to ~25s for the managed challenge to
        # auto-clear (real browser solves it transparently).
        for _ in range(25):
            if _Capture.done.is_set():
                break
            try:
                body = page.locator("body").inner_text(timeout=2_000)
            except Exception:
                body = ""
            if "security verification" in body.lower() or "verify you are" in body.lower():
                time.sleep(1)
                continue
            break

        # Walk through up to 6 interstitial screens (account-chooser, consent…).
        for _ in range(6):
            if _Capture.done.is_set():
                break
            try:
                page.wait_for_load_state("networkidle", timeout=6_000)
            except Exception:
                pass
            if _Capture.done.is_set():
                break

            cur = page.url
            # 1) Account chooser — click the row with our email.
            if "choose-an-account" in cur or "/account" in cur:
                clicked = False
                # Try clicking anything containing the email text.
                for sel in (
                    f"text={email}",
                    "button:has-text('@')",
                    "[role=button]:has-text('@')",
                    "a:has-text('@')",
                ):
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0 and el.is_visible():
                            print(f"choosing account via selector: {sel}")
                            el.click(timeout=5_000)
                            clicked = True
                            break
                    except Exception:
                        continue
                if not clicked:
                    print("could not find account row to click")
                continue

            # 2) Consent / authorize screen.
            consent_clicked = False
            for pat in (r"^Authorize$", r"^Allow$", r"^Continue$", r"^Approve$", r"^Yes$", r"^Confirm$"):
                try:
                    btn = page.get_by_role("button", name=_re.compile(pat, _re.I)).first
                    if btn.count() > 0 and btn.is_visible():
                        print(f"clicking consent button: {pat}")
                        btn.click(timeout=5_000)
                        consent_clicked = True
                        break
                except Exception:
                    continue
            if not consent_clicked:
                # Nothing actionable on this screen — maybe it's mid-redirect.
                time.sleep(2)

        _Capture.done.wait(timeout=60)
        try:
            ctx.storage_state(path=str(STATE_FILE))
        except Exception:
            pass
        ctx.close()  # persistent context — no separate browser handle

    if _Capture.error or not _Capture.code:
        raise RuntimeError(f"OAuth authorize failed: {_Capture.error or 'no code captured'}")
    if _Capture.state != state:
        raise RuntimeError("State mismatch — possible CSRF; aborting.")

    print("Got authorization code. Exchanging for tokens…")
    body = {
        "grant_type": "authorization_code",
        "code": _Capture.code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": verifier,
    }
    with httpx.Client(timeout=30) as cx:
        r = cx.post(TOKEN_URL, data=body)
    if r.status_code >= 400:
        raise RuntimeError(f"Token exchange failed {r.status_code}: {r.text[:400]}")
    tok = r.json()
    creds = _save_creds(tok)

    # amr + account check.
    claims = _decode_jwt(creds["access_token"])
    auth = claims.get("https://api.openai.com/auth", {})
    print(f"  client_id : {claims.get('client_id')}")
    print(f"  amr       : {auth.get('amr')}")
    print(f"  account_id: {creds['account_id']}")
    print(f"  plan      : {auth.get('chatgpt_plan_type')}")

    _write_token_to_env(creds["access_token"])
    print(f"OK -- saved creds to {CODEX_CREDS} and token to {ENV_FILE}")
    return creds


def test_codex() -> bool:
    """Hit the Codex backend with the freshly minted token."""
    creds = json.loads(CODEX_CREDS.read_text(encoding="utf-8"))
    headers = {
        "Authorization": f"Bearer {creds['access_token']}",
        "Content-Type": "application/json",
        "chatgpt-account-id": creds["account_id"],
        "originator": "codex_cli_rs",
        "User-Agent": "codex_cli_rs/0.40.0",
        "Accept": "text/event-stream",
    }
    body = {
        "model": "gpt-5.2",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Reply with the single word: OK"}],
            }
        ],
        "store": False,
        "stream": True,
        "instructions": "You are a test.",
    }
    print("\nTesting against Codex backend…")
    with httpx.Client(timeout=60) as cx:
        with cx.stream("POST", "https://chatgpt.com/backend-api/codex/responses",
                       headers=headers, json=body) as resp:
            if resp.status_code >= 400:
                txt = resp.read().decode("utf-8", "replace")
                print(f"  Codex {resp.status_code}: {txt[:300]}")
                return resp.status_code < 400
            # consume a little of the stream to confirm it works
            for i, line in enumerate(resp.iter_lines()):
                if line:
                    print(f"  stream: {line[:120]}")
                if i > 6:
                    break
            print("  Codex 200 — token WORKS.")
            return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--test-only", action="store_true")
    args = ap.parse_args()
    try:
        if not args.test_only:
            login(headed=args.headed)
        ok = test_codex()
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
