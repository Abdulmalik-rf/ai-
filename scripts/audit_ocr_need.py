"""Walk every PDF in data/drive_raw/ and decide whether it needs OCR.

A PDF "has clean text" when:
  - The first 6 pages extract ≥600 chars
  - ≥30% of those chars are Arabic / Latin letters
  - ≥3 common Arabic stop-words appear

Anything failing those checks needs OCR. Prints a summary plus per-file
status so we can spot-check before spending CPU time.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "drive_raw"
OCR_PDF = ROOT / "data" / "ocr_pdf"

_PROBE = (
    "في ", "من ", "إلى", "على", "عن ", "كان", "هذا", "هذه",
    "مادة", "نظام", "محكمة", "قضاء", "حكم", "قانون", "وزارة", "المملكة",
)


def has_clean_text(path: Path) -> tuple[bool, dict]:
    info = {"chars": 0, "arabic_ratio": 0.0, "probe_hits": 0}
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
        info["chars"] = len(text)
        if len(text) < 600:
            return False, info
        non_ws = sum(1 for c in text if not c.isspace())
        if not non_ws:
            return False, info
        arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 0x0250)
        info["arabic_ratio"] = round((arabic + latin) / non_ws, 2)
        if info["arabic_ratio"] < 0.3:
            return False, info
        info["probe_hits"] = sum(1 for w in _PROBE if w in text)
        return info["probe_hits"] >= 3, info
    except Exception as exc:  # noqa: BLE001
        info["error"] = repr(exc)
        return False, info


def main() -> None:
    pdfs = sorted(RAW.glob("*.pdf"))
    clean: list[Path] = []
    needs_ocr: list[Path] = []
    cached_ocr: list[Path] = []

    for p in pdfs:
        ok, info = has_clean_text(p)
        if ok:
            clean.append(p)
        else:
            ocr_done = (OCR_PDF / p.name).exists()
            (cached_ocr if ocr_done else needs_ocr).append(p)

    print(f"Total PDFs:           {len(pdfs)}")
    print(f"  Clean (no OCR):     {len(clean)}")
    print(f"  Already OCR'd:      {len(cached_ocr)}")
    print(f"  Needs OCR:          {len(needs_ocr)}")
    print()
    print("=== Files needing OCR (first 30) ===")
    for p in needs_ocr[:30]:
        print(f"  {p.name}  ({p.stat().st_size//1024} KB)")
    if len(needs_ocr) > 30:
        print(f"  ...and {len(needs_ocr)-30} more")


if __name__ == "__main__":
    main()
