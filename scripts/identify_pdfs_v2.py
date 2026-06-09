"""Try pdfplumber for files where pypdf returned empty text."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pdfplumber

RAW = Path(__file__).resolve().parent.parent / "data" / "drive_raw"


def extract(path: Path) -> dict:
    info = {
        "filename": path.name,
        "size_kb": round(path.stat().st_size / 1024, 1),
        "page_count": None,
        "first_chars": "",
        "error": None,
    }
    try:
        with pdfplumber.open(str(path)) as pdf:
            info["page_count"] = len(pdf.pages)
            text = ""
            for i, page in enumerate(pdf.pages):
                if i >= 3:
                    break
                try:
                    t = page.extract_text() or ""
                except Exception:  # noqa: BLE001
                    t = ""
                text += t + "\n"
                if len(text) > 1500:
                    break
            info["first_chars"] = text.strip()[:500]
    except Exception as exc:  # noqa: BLE001
        info["error"] = repr(exc)
    return info


def main() -> None:
    files = sorted(RAW.glob("*.pdf"))
    out = [extract(p) for p in files]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
