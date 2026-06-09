"""List the documents whose embedded text is high-quality (no OCR needed),
ordered by domain, with the title extracted from page 1.

These are the rock-solid sources — ingestion preserves them 100% verbatim,
so the agent can quote them word-for-word.
"""
from __future__ import annotations
import re, sys, unicodedata
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "drive_raw"

import fitz

_PROBE = (
    "في ", "من ", "إلى", "على", "عن ", "كان", "هذا", "هذه",
    "مادة", "نظام", "محكمة", "قضاء", "حكم", "قانون", "وزارة", "المملكة",
)


def is_clean(path: Path) -> bool:
    try:
        with fitz.open(str(path)) as doc:
            text = ""
            for i, page in enumerate(doc):
                if i >= 6:
                    break
                text += page.get_text("text") or ""
                if len(text) > 4000:
                    break
        text = text.strip()
        if len(text) < 600:
            return False
        non_ws = sum(1 for c in text if not c.isspace())
        if not non_ws:
            return False
        arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 0x0250)
        if (arabic + latin) / non_ws < 0.3:
            return False
        return sum(1 for w in _PROBE if w in text) >= 3
    except Exception:
        return False


def title_guess(path: Path) -> str:
    try:
        with fitz.open(str(path)) as doc:
            text = (doc[0].get_text("text") or "")[:800]
    except Exception:
        return path.stem
    # First plausible Arabic line >= 10 chars, <= 120
    for line in text.splitlines():
        s = line.strip()
        if 10 <= len(s) <= 140 and re.search(r"[؀-ۿ]", s):
            return s
    return path.stem


def main() -> None:
    clean: list[tuple[str, int, str, Path]] = []
    for p in sorted(RAW.glob("*.pdf")):
        if not is_clean(p):
            continue
        with fitz.open(str(p)) as doc:
            n_pages = len(doc)
        title = title_guess(p)
        clean.append((title, n_pages, p.stem, p))

    print(f"Clean-text documents: {len(clean)} / 196 total")
    print()
    for title, pages, stem, p in sorted(clean, key=lambda x: -x[1]):
        print(f"  [{pages:>4}p]  {title}")


if __name__ == "__main__":
    main()
