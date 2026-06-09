"""Attempt to enable Codex backend access on the ChatGPT account by
programmatically completing any enrollment / onboarding flow.

Visits the candidate enrollment URLs in order, looks for visible
'Get started' / 'Try Codex' / 'Enable' / 'Accept' buttons, clicks them,
captures the page state, and reports back.

Run after a working session has been stored by chatgpt_token_refresh.py
(it reuses the same .playwright_state.json).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

API_DIR = Path(__file__).resolve().parent.parent / "apps" / "api"
STATE_FILE = API_DIR / ".playwright_state.json"

# Order matters — try the most likely enrollment URL first.
CANDIDATE_URLS = [
    "https://chatgpt.com/codex",
    "https://chatgpt.com/codex/onboarding",
    "https://platform.openai.com/codex",
    "https://platform.openai.com/codex/onboarding",
    "https://chatgpt.com/g/g-codex",
]

CTA_PATTERNS = [
    r"^Get started$",
    r"^Try Codex( CLI)?$",
    r"^Enable( Codex)?$",
    r"^Accept( terms)?$",
    r"^Continue$",
    r"^I agree$",
    r"^Enroll$",
    r"^Activate( Codex)?$",
]


def main() -> int:
    if not STATE_FILE.exists():
        print(f"No saved session at {STATE_FILE}. Run chatgpt_token_refresh.py --headed first.", file=sys.stderr)
        return 1

    findings: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        for url in CANDIDATE_URLS:
            print(f"\n--- {url} ---")
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception as exc:
                print(f"  navigation error: {exc}")
                findings.append(f"{url}: navigation error")
                continue

            status = resp.status if resp else "?"
            print(f"  HTTP {status}  final={page.url}")

            # Small settle for SPA hydration.
            try:
                page.wait_for_load_state("networkidle", timeout=8_000)
            except Exception:
                pass

            title = page.title()
            print(f"  title: {title!r}")
            findings.append(f"{url}: {status} | title={title!r}")

            # Snapshot a small piece of body text so we can see what's there.
            try:
                body_text = page.locator("body").inner_text(timeout=5_000)
            except Exception:
                body_text = ""
            preview = re.sub(r"\s+", " ", body_text[:300]).strip()
            print(f"  body preview: {preview!r}")

            # Try every CTA pattern — first one that matches & clicks wins.
            for pat in CTA_PATTERNS:
                try:
                    btn = page.get_by_role("button", name=re.compile(pat, re.I)).first
                    if btn.count() > 0 and btn.is_visible():
                        text = btn.inner_text(timeout=2_000)
                        print(f"  clicking button: {text!r}")
                        btn.click(timeout=6_000)
                        try:
                            page.wait_for_load_state("networkidle", timeout=10_000)
                        except Exception:
                            pass
                        findings.append(f"  clicked {text!r}")
                        break
                except Exception as exc:
                    continue

            # If we got here, screenshot for debugging.
            try:
                Path("data").mkdir(exist_ok=True)
                shot = Path("data") / f"codex_{re.sub(r'[^a-z0-9]+', '_', url.lower())[:60]}.png"
                page.screenshot(path=str(shot), full_page=True)
                print(f"  screenshot: {shot}")
            except Exception:
                pass

        # Persist any new cookies / state.
        ctx.storage_state(path=str(STATE_FILE))
        browser.close()

    print("\n=== Summary ===")
    for line in findings:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
