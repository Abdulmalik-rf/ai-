"""Try PyMuPDF (fitz) — usually best for Arabic + scanned-with-text PDFs."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

RAW = Path(__file__).resolve().parent.parent / "data" / "drive_raw"


def extract(path: Path) -> dict:
    info = {
        "filename": path.name,
        "size_kb": round(path.stat().st_size / 1024, 1),
        "page_count": None,
        "first_chars": "",
        "has_text": False,
        "has_images": False,
        "error": None,
    }
    try:
        doc = fitz.open(str(path))
        info["page_count"] = len(doc)
        text = ""
        any_image = False
        for i, page in enumerate(doc):
            if i >= 3:
                break
            t = page.get_text("text") or ""
            text += t + "\n"
            if page.get_images():
                any_image = True
            if len(text) > 1500:
                break
        info["first_chars"] = text.strip()[:500]
        info["has_text"] = bool(text.strip())
        info["has_images"] = any_image
        doc.close()
    except Exception as exc:  # noqa: BLE001
        info["error"] = repr(exc)
    return info


def main() -> None:
    files = sorted(RAW.glob("*.pdf"))
    out = [extract(p) for p in files]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
