"""One-click Google OAuth flow for Gemini CLI's client_id.

Generates the authorize URL with PKCE, spins up a localhost callback server,
opens your browser, captures the redirect, exchanges the code, and writes
the credentials to apps/api/.gemini_oauth.json.

Usage:
    python scripts/gemini_oauth_login.py

Then sign in to your Google account, accept the scopes, and you're done.
The script writes:
    {
      "access_token":  "ya29...",
      "refresh_token": "1//...",
      "expiry":        "2026-05-25T16:42:00Z",
      "scope":         "...",
      "token_type":    "Bearer",
      "id_token":      "..."
    }

Our backend reads that file and auto-refreshes via the refresh_token when
the access_token expires — you never have to re-run this script.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

# ── Gemini CLI's public OAuth client (a native/installed-app client). ───────
# The client_secret for installed-app OAuth is NOT confidential — it ships in
# the open-source Gemini CLI binary. Kept out of the repo to satisfy secret
# scanners; supply it via env (the public value is in the Gemini CLI source).
CLIENT_ID = "681255809395-oo8ft2oprdrnp9e3aqf6av3hmdib135j.apps.googleusercontent.com"
CLIENT_SECRET = os.environ.get("GEMINI_OAUTH_CLIENT_SECRET", "")
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/oauth2callback"
SCOPES = " ".join([
    "https://www.googleapis.com/auth/cloud-platform",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
])

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

OUT = Path(__file__).resolve().parent.parent / "apps" / "api" / ".gemini_oauth.json"


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def make_pkce() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


# ────────────────────────────────────────────────────────────────────────────
# Local callback server — captures the ?code= and the optional ?error=
# ────────────────────────────────────────────────────────────────────────────

class _State:
    code: str | None = None
    error: str | None = None
    done = threading.Event()


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/oauth2callback":
            self.send_response(404)
            self.end_headers()
            return
        q = urllib.parse.parse_qs(parsed.query)
        _State.code = (q.get("code") or [None])[0]
        _State.error = (q.get("error") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        page = (
            "<!doctype html><meta charset='utf-8'><title>Gemini auth</title>"
            "<style>body{font-family:system-ui;padding:48px;text-align:center;"
            "background:#0f172a;color:#e2e8f0}h1{font-size:32px;margin:0 0 8px}"
            "p{color:#94a3b8;font-size:14px}.ok{color:#22c55e}.bad{color:#ef4444}"
            "</style>"
            + (
                "<h1 class='bad'>✗ Sign-in failed</h1><p>" + (_State.error or "")
                + "</p><p>You can close this tab.</p>"
                if _State.error else
                "<h1 class='ok'>✓ Signed in</h1>"
                "<p>Your Gemini token is being saved. You can close this tab.</p>"
            )
        )
        self.wfile.write(page.encode("utf-8"))
        _State.done.set()

    def log_message(self, *_):  # silence default access-log spam
        pass


def serve_once() -> None:
    with socketserver.TCPServer(("127.0.0.1", REDIRECT_PORT), _Handler) as srv:
        srv.timeout = 1.0
        while not _State.done.is_set():
            srv.handle_request()


# ────────────────────────────────────────────────────────────────────────────
# Main flow
# ────────────────────────────────────────────────────────────────────────────

def main() -> int:
    verifier, challenge = make_pkce()
    state = _b64url(secrets.token_bytes(16))

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    auth_url = AUTH_URL + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    print("=" * 78)
    print("Google OAuth — Gemini CLI client_id")
    print("=" * 78)
    print()
    print("Opening browser… If it doesn't open automatically, click here:")
    print()
    print(auth_url)
    print()
    print("Waiting for redirect on http://localhost:" + str(REDIRECT_PORT) + " …")
    print()

    t = threading.Thread(target=serve_once, daemon=True)
    t.start()

    try:
        webbrowser.open(auth_url, new=2)
    except Exception:  # noqa: BLE001
        pass

    # Wait for the redirect.
    if not _State.done.wait(timeout=600):
        print("Timed out after 10 minutes. Re-run the script.")
        return 2
    t.join(timeout=2)

    if _State.error or not _State.code:
        print(f"OAuth error: {_State.error or 'no code returned'}")
        return 1

    # Exchange the code for tokens.
    print("Exchanging authorization code for tokens…")
    body = {
        "grant_type": "authorization_code",
        "code": _State.code,
        "code_verifier": verifier,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    with httpx.Client(timeout=30) as cx:
        r = cx.post(TOKEN_URL, data=body)
    if r.status_code >= 400:
        print(f"Token exchange failed: {r.status_code} {r.text[:400]}")
        return 1
    tok = r.json()

    expires_in = int(tok.get("expires_in", 3600))
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 30)

    creds = {
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "id_token": tok.get("id_token"),
        "scope": tok.get("scope"),
        "token_type": tok.get("token_type", "Bearer"),
        "expiry": expiry.isoformat(),
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(creds, indent=2), encoding="utf-8")
    # Lock down perms (best-effort on Windows; .env-style sensitivity).
    try:
        os.chmod(OUT, 0o600)
    except Exception:  # noqa: BLE001
        pass

    # Use ASCII-only output so Windows cp1252 console doesn't crash on emoji.
    print()
    print("=" * 78)
    print(f"OK -- saved credentials -> {OUT}")
    print("=" * 78)
    print()
    print(f"  access_token expires at:  {expiry.isoformat()}")
    print(f"  refresh_token present:    {'yes' if tok.get('refresh_token') else 'NO -- re-run with prompt=consent'}")
    print()
    print("Next: wire the backend to read this file and auto-refresh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
