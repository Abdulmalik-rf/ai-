#!/usr/bin/env bash
# Run AFTER scripts/ocr_pdfs.py (initial pass) finishes.
# Force-OCR the 5 PDFs whose embedded text is CID-glyph-encoded (we still
# have to read them but the text-layer extraction is unusable for chunking).
#
# Filenames are matched NFC-normalized inside the OCR script, so passing the
# composed-form Arabic literals works on Windows + Git Bash.
set -e
cd "$(dirname "$0")/.."

PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  apps/api/.venv/Scripts/python.exe scripts/ocr_pdfs.py \
  --re-do \
  --files \
    "1.pdf" \
    "50.pdf" \
    "0jSlLnxiPkSM5f70l.pdf" \
    "E3whWapFW1smFNaut.pdf" \
    "5ld2cEfJ2ESFQiZM1.pdf"
