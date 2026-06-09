"""Score every staged document and flag those with low-quality text.

For each PDF in data/corpus_final (i.e. what was actually ingested), pull
the embedded text from PyMuPDF and rate it on three signals:
  - char_count:       any content at all?
  - arabic_word_hits: count of common Arabic stop/structure words
  - cid_ratio:        fraction of "characters that look CID-garbled"
                      (private-use codepoints, control chars)

Prints a sorted list of the worst offenders so the user can decide which to
re-OCR or replace.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus_final"
RAW = ROOT / "data" / "drive_raw"
OCR_TEXT = ROOT / "data" / "ocr_text"
OCR_PDF = ROOT / "data" / "ocr_pdf"

PROBE = (
    "في ", "من ", "إلى", "على", "عن ", "كان", "هذا", "هذه",
    "مادة", "نظام", "محكمة", "قضاء", "حكم", "قانون", "وزارة", "المملكة",
    "المادة", "الفصل", "الباب", "اللائحة", "القرار", "المرسوم",
)


def sample_text(path: Path, pages: int = 10, max_chars: int = 12000) -> str:
    try:
        with fitz.open(str(path)) as doc:
            txt = ""
            for i, pg in enumerate(doc):
                if i >= pages:
                    break
                txt += pg.get_text("text") or ""
                if len(txt) > max_chars:
                    break
        return txt
    except Exception as exc:  # noqa: BLE001
        return ""


def score(text: str) -> dict:
    s = text or ""
    if not s:
        return {"chars": 0, "arabic_words": 0, "noise_ratio": 1.0, "quality": "EMPTY"}
    non_ws = sum(1 for c in s if not c.isspace())
    arabic = sum(1 for c in s if "؀" <= c <= "ۿ")
    # "Noise": replacement char, control chars, private-use, weird symbols.
    noise = sum(
        1 for c in s
        if c in ("�", "\x00") or
        unicodedata.category(c) in ("Co", "Cn") or
        (0x2000 <= ord(c) <= 0x206F and c not in " \t\n")
    )
    noise_ratio = noise / non_ws if non_ws else 1.0
    hits = sum(1 for w in PROBE if w in s)
    arabic_ratio = arabic / non_ws if non_ws else 0
    if hits >= 5 and arabic_ratio >= 0.3 and noise_ratio < 0.05:
        q = "GOOD"
    elif hits >= 2:
        q = "MEDIUM"
    elif arabic_ratio > 0.2:
        q = "POOR (garbled / CID encoded)"
    else:
        q = "POOR (no Arabic text)"
    return {
        "chars": len(s),
        "arabic_words": hits,
        "noise_ratio": round(noise_ratio, 3),
        "arabic_ratio": round(arabic_ratio, 2),
        "quality": q,
    }


def main() -> None:
    rows: list[dict] = []
    for pdf in sorted(CORPUS.rglob("*.pdf")):
        text = sample_text(pdf)
        info = score(text)
        info["title"] = pdf.relative_to(CORPUS).as_posix()
        rows.append(info)

    # bucket
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(r["quality"], []).append(r)

    print(f"Total ingested files: {len(rows)}")
    for k in ("GOOD", "MEDIUM", "POOR (garbled / CID encoded)", "POOR (no Arabic text)", "EMPTY"):
        print(f"  {k:35s} {len(buckets.get(k, []))}")
    print()

    bad_keys = [k for k in buckets if k != "GOOD"]
    for k in bad_keys:
        print(f"=== {k} ({len(buckets[k])}) ===")
        for r in sorted(buckets[k], key=lambda x: x["arabic_words"]):
            print(
                f"  hits={r['arabic_words']:>2}  "
                f"noise={r['noise_ratio']:.3f}  "
                f"arabic={r['arabic_ratio']:.2f}  "
                f"chars={r['chars']:>6}  "
                f"{r['title']}"
            )
        print()


if __name__ == "__main__":
    main()
