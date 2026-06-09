"""Identify each PDF in data/drive_raw/ by extracting text from the first 1-2 pages.

Outputs JSON to stdout with: filename, title_guess, first_chars, page_count, size.
The title guess looks at PDF metadata title, then the first non-empty line.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pypdf

RAW = Path(__file__).resolve().parent.parent / "data" / "drive_raw"


def identify(path: Path) -> dict:
    info: dict = {
        "filename": path.name,
        "size_kb": round(path.stat().st_size / 1024, 1),
        "title_meta": None,
        "title_guess": None,
        "first_chars": None,
        "page_count": None,
        "error": None,
    }
    try:
        reader = pypdf.PdfReader(str(path))
        info["page_count"] = len(reader.pages)
        meta = reader.metadata or {}
        info["title_meta"] = (meta.title or "").strip() or None

        text = ""
        for i, page in enumerate(reader.pages):
            if i >= 2:
                break
            try:
                t = page.extract_text() or ""
            except Exception:  # noqa: BLE001
                t = ""
            text += t + "\n"
            if len(text) > 1500:
                break

        text = text.strip()
        info["first_chars"] = text[:600]

        # Title guess: first non-empty short line that looks like a title
        for line in text.splitlines():
            s = line.strip()
            if 5 <= len(s) <= 200 and not s.endswith(":"):
                info["title_guess"] = s
                break
    except Exception as exc:  # noqa: BLE001
        info["error"] = repr(exc)
    return info


def main() -> None:
    files = sorted(RAW.glob("*.pdf"))
    out = [identify(p) for p in files]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
