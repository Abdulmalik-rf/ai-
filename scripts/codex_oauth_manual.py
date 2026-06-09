"""Manual-assist Codex OAuth: you open the URL in YOUR normal browser.

Cloudflare's Turnstile blocks automated browsers but passes instantly for a
real, already-logged-in browser. So instead of driving Playwright, this
script just:
  1. Generates PKCE + state and prints the authorize URL.
  2. Runs the localhost:1455 callback server.
  3. Waits for YOU to open the URL, click through account/consent.
  4. Captures the redirect's ?code=, exchanges it for tokens, saves them to
     apps/api/.codex_oauth.json + writes the access_token into .env.

Run it, then open the printed URL in Edge/Chrome where you're logged into
the ChatGPT account (mmvcnbdb@telegmail.com).
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import sys
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

API_DIR = Path(__file__).resolve().parent.parent / "apps" / "api"
ENV_FILE = API_DIR / ".env"
CODEX_CREDS = API_DIR / ".codex_oauth.json"

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
REDIRECT_PORT = 1455
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/auth/callback"
SCOPE = "openid profile email offline_access"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _decode_jwt(t: str) -> dict:
    pb = t.split(".")[1] + "=" * (-len(t.split(".")[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(pb).decode("utf-8"))


class _Cap:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    done = threading.Event()


class _H(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        if u.path != "/auth/callback":
            self.send_response(404)
            self.end_headers()
            return
        q = urllib.parse.parse_qs(u.query)
        _Cap.code = (q.get("code") or [None])[0]
        _Cap.state = (q.get("state") or [None])[0]
        _Cap.error = (q.get("error") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = bool(_Cap.code and not _Cap.error)
        self.wfile.write(
            (
                "<!doctype html><meta charset=utf-8><title>Codex</title>"
                "<body style='font-family:system-ui;background:#0f172a;color:#e2e8f0;"
                "text-align:center;padding:64px'>"
                + ("<h1 style='color:#22c55e'>Token captured</h1><p>Done — you can close this tab and return to the terminal.</p>"
                   if ok else
                   f"<h1 style='color:#ef4444'>Failed</h1><p>{_Cap.error or 'no code'}</p>")
                + "</body>"
            ).encode("utf-8")
        )
        _Cap.done.set()

    def log_message(self, *_):
        pass


def _write_env(token: str) -> None:
    text = ENV_FILE.read_text(encoding="utf-8")
    pat = re.compile(r"^OPENAI_CHATGPT_TOKEN=.*$", re.MULTILINE)
    text = pat.sub(f"OPENAI_CHATGPT_TOKEN={token}", text) if pat.search(text) else text + f"\nOPENAI_CHATGPT_TOKEN={token}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


def main() -> int:
    verifier, challenge = _b64(secrets.token_bytes(64)), None
    challenge = _b64(hashlib.sha256(verifier.encode("ascii")).digest())
    state = _b64(secrets.token_bytes(16))
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
    url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    srv = HTTPServer(("127.0.0.1", REDIRECT_PORT), _H)
    srv.timeout = 1.0
    t = threading.Thread(
        target=lambda: [srv.handle_request() for _ in iter(lambda: not _Cap.done.is_set(), False)],
        daemon=True,
    )
    t.start()

    print("\n" + "=" * 78)
    print("OPEN THIS URL IN YOUR NORMAL BROWSER (logged into the ChatGPT account):")
    print("=" * 78 + "\n")
    print(url + "\n")
    print("Waiting for you to sign in / approve … (30 min timeout)\n")

    if not _Cap.done.wait(timeout=1800):
        print("Timed out. Re-run and open the URL faster.", file=sys.stderr)
        return 2
    if _Cap.error or not _Cap.code:
        print(f"OAuth failed: {_Cap.error or 'no code'}", file=sys.stderr)
        return 1
    if _Cap.state != state:
        print("State mismatch — aborting.", file=sys.stderr)
        return 1

    print("Got the code. Exchanging for tokens…")
    with httpx.Client(timeout=30) as cx:
        r = cx.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": _Cap.code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": verifier,
        })
    if r.status_code >= 400:
        print(f"Token exchange failed {r.status_code}: {r.text[:300]}", file=sys.stderr)
        return 1
    tok = r.json()

    access = tok["access_token"]
    id_token = tok.get("id_token", "")
    account_id = ""
    for jwt in (id_token, access):
        if not jwt:
            continue
        try:
            account_id = _decode_jwt(jwt).get("https://api.openai.com/auth", {}).get("chatgpt_account_id", "")
        except Exception:
            pass
        if account_id:
            break

    expires_in = int(tok.get("expires_in", 0))
    creds = {
        "access_token": access,
        "refresh_token": tok.get("refresh_token", ""),
        "id_token": id_token,
        "account_id": account_id,
        "client_id": CLIENT_ID,
        "expiry": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat() if expires_in else None,
    }
    CODEX_CREDS.write_text(json.dumps(creds, indent=2), encoding="utf-8")
    _write_env(access)

    claims = _decode_jwt(access)
    auth = claims.get("https://api.openai.com/auth", {})
    exp = claims.get("exp")
    print("\n" + "=" * 78)
    print("OK -- token minted and saved.")
    print(f"  client_id : {claims.get('client_id')}")
    print(f"  plan      : {auth.get('chatgpt_plan_type')}")
    print(f"  account_id: {account_id}")
    print(f"  refresh   : {'yes' if creds['refresh_token'] else 'NO'}")
    if exp:
        print(f"  expires   : {datetime.fromtimestamp(int(exp), tz=timezone.utc).isoformat()}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
