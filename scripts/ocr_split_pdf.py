"""OCR a very large PDF by splitting it into N-page slices, OCRing each
slice as an isolated subprocess, then concatenating the results into the
canonical data/ocr_text/<stem>.txt and data/ocr_pdf/<file>.pdf locations.

Used as a workaround for files that exceed the per-file timeout in
scripts/ocr_pdfs_resilient.py — 318+ page judgment books, etc. Each slice
gets its own 30-min wall-clock budget, so a laptop sleep or transient
easyocr stall only loses one slice, not the whole document.
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
import unicodedata
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "drive_raw"
OUT_TEXT = ROOT / "data" / "ocr_text"
OUT_PDF = ROOT / "data" / "ocr_pdf"
SLICE_TEMP = ROOT / "data" / "ocr_slices"
VENV_PY = ROOT / "apps" / "api" / ".venv" / "Scripts" / "python.exe"
WORKER = ROOT / "scripts" / "ocr_one_file.py"

OUT_TEXT.mkdir(parents=True, exist_ok=True)
OUT_PDF.mkdir(parents=True, exist_ok=True)


def find_source(name: str) -> Path:
    target_nfc = unicodedata.normalize("NFC", name)
    for p in RAW.iterdir():
        if p.is_file() and unicodedata.normalize("NFC", p.name) == target_nfc:
            return p
    raise FileNotFoundError(name)


def slice_pdf(src: Path, out_dir: Path, pages_per_slice: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with fitz.open(str(src)) as doc:
        n = len(doc)
        slices: list[Path] = []
        for start in range(0, n, pages_per_slice):
            end = min(start + pages_per_slice - 1, n - 1)
            sub = fitz.open()
            sub.insert_pdf(doc, from_page=start, to_page=end)
            slice_path = out_dir / f"{src.stem}__p{start+1:04d}-{end+1:04d}.pdf"
            sub.save(str(slice_path), deflate=True)
            sub.close()
            slices.append(slice_path)
    return slices


def ocr_slice(slice_pdf_path: Path, dpi: int, timeout_s: int) -> tuple[Path, Path, bool]:
    out_txt = SLICE_TEMP / (slice_pdf_path.stem + ".txt")
    out_pdf = SLICE_TEMP / (slice_pdf_path.stem + ".pdf")
    if out_txt.exists() and out_txt.stat().st_size > 50 \
       and out_pdf.exists() and out_pdf.stat().st_size > 1024:
        return out_txt, out_pdf, True  # cached
    cmd = [
        str(VENV_PY), str(WORKER),
        "--src", str(slice_pdf_path),
        "--out-txt", str(out_txt),
        "--out-pdf", str(out_pdf),
        "--dpi", str(dpi),
    ]
    try:
        res = subprocess.run(
            cmd,
            env={
                **__import__("os").environ,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            },
            timeout=timeout_s,
            check=False,
        )
        return out_txt, out_pdf, res.returncode == 0
    except subprocess.TimeoutExpired:
        return out_txt, out_pdf, False


def concatenate_text(slice_txts: list[Path], out_txt: Path) -> None:
    parts: list[str] = []
    for p in slice_txts:
        if p.exists():
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
        else:
            parts.append(f"\n--- (slice missing: {p.name}) ---\n")
    out_txt.write_text("\n".join(parts), encoding="utf-8")


def concatenate_pdfs(slice_pdfs: list[Path], out_pdf: Path) -> None:
    merged = fitz.open()
    for p in slice_pdfs:
        if p.exists():
            with fitz.open(str(p)) as sub:
                merged.insert_pdf(sub)
    merged.save(str(out_pdf), deflate=True)
    merged.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True,
                        help="Source filename inside data/drive_raw/")
    parser.add_argument("--pages-per-slice", type=int, default=50)
    parser.add_argument("--slice-timeout-min", type=float, default=30)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    src = find_source(args.file)
    print(f"Source: {src.name}")
    src_slice_dir = SLICE_TEMP / src.stem
    slices = slice_pdf(src, src_slice_dir, args.pages_per_slice)
    print(f"Sliced into {len(slices)} parts.", flush=True)

    slice_txts: list[Path] = []
    slice_pdfs_out: list[Path] = []
    for i, sp in enumerate(slices, 1):
        print(f"[{i}/{len(slices)}] OCR slice {sp.name}", flush=True)
        out_txt, out_pdf, ok = ocr_slice(sp, args.dpi, int(args.slice_timeout_min * 60))
        slice_txts.append(out_txt)
        slice_pdfs_out.append(out_pdf)
        status = "ok" if ok else "FAILED/TIMEOUT"
        print(f"   slice -> {status}", flush=True)

    out_txt_final = OUT_TEXT / (src.stem + ".txt")
    out_pdf_final = OUT_PDF / src.name
    concatenate_text(slice_txts, out_txt_final)
    concatenate_pdfs(slice_pdfs_out, out_pdf_final)
    print(f"\nMerged -> {out_txt_final.name} + {out_pdf_final.name}", flush=True)
    if out_pdf_final.exists():
        print(f"   PDF size: {out_pdf_final.stat().st_size//1024//1024} MB", flush=True)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
