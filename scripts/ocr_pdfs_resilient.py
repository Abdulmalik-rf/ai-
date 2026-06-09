"""Resilient batch OCR driver.

Iterates every PDF in data/drive_raw/ that lacks clean text AND lacks a
cached OCR output, and spawns scripts/ocr_one_file.py as a subprocess per
file with a per-file wall-clock timeout. If a single file hangs, we kill it,
log the failure to data/ocr_failed.txt, and move on — one bad file no longer
stalls the whole queue.

Resumable: outputs in data/ocr_pdf and data/ocr_text are cached.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "drive_raw"
OUT_TEXT = ROOT / "data" / "ocr_text"
OUT_PDF = ROOT / "data" / "ocr_pdf"
FAIL_LOG = ROOT / "data" / "ocr_failed.txt"
VENV_PY = ROOT / "apps" / "api" / ".venv" / "Scripts" / "python.exe"
WORKER = ROOT / "scripts" / "ocr_one_file.py"

OUT_TEXT.mkdir(parents=True, exist_ok=True)
OUT_PDF.mkdir(parents=True, exist_ok=True)


_PROBE = (
    "في ", "من ", "إلى", "على", "عن ", "كان", "هذا", "هذه",
    "مادة", "نظام", "محكمة", "قضاء", "حكم", "قانون", "وزارة", "المملكة",
)


def has_clean_text(path: Path, sample_pages: int = 6) -> bool:
    try:
        with fitz.open(str(path)) as doc:
            text = ""
            for i, page in enumerate(doc):
                if i >= sample_pages:
                    break
                text += page.get_text("text") or ""
                if len(text) > 4000:
                    break
        text = text.strip()
        if len(text) < 600:
            return False
        non_ws = sum(1 for c in text if not c.isspace())
        arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 0x0250)
        if not non_ws or (arabic + latin) / non_ws < 0.3:
            return False
        return sum(1 for w in _PROBE if w in text) >= 3
    except Exception:  # noqa: BLE001
        return False


def cached(p: Path) -> bool:
    txt = OUT_TEXT / (p.stem + ".txt")
    pdf = OUT_PDF / p.name
    return (
        txt.exists() and txt.stat().st_size > 50
        and pdf.exists() and pdf.stat().st_size > 1024
    )


def load_failed() -> set[str]:
    if not FAIL_LOG.exists():
        return set()
    return {
        unicodedata.normalize("NFC", l.strip())
        for l in FAIL_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
        if l.strip()
    }


def append_failed(name: str, reason: str) -> None:
    with FAIL_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{name}\t{reason}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--per-file-timeout-min", type=float, default=20,
                        help="Kill the OCR worker if a single file exceeds this many minutes.")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Retry files previously logged in ocr_failed.txt.")
    args = parser.parse_args()

    timeout_s = int(args.per_file_timeout_min * 60)
    failed = set() if args.retry_failed else load_failed()

    queue: list[Path] = []
    for src in sorted(RAW.glob("*.pdf")):
        if cached(src):
            continue
        if has_clean_text(src):
            continue
        if unicodedata.normalize("NFC", src.name) in failed:
            print(f"skip (previously failed): {src.name}", flush=True)
            continue
        queue.append(src)

    print(f"queue: {len(queue)} files, per-file timeout {args.per_file_timeout_min} min\n", flush=True)

    for idx, src in enumerate(queue, 1):
        out_txt = OUT_TEXT / (src.stem + ".txt")
        out_pdf = OUT_PDF / src.name
        print(f"[{idx}/{len(queue)}] {src.name}", flush=True)

        t0 = time.time()
        try:
            res = subprocess.run(
                [
                    str(VENV_PY), str(WORKER),
                    "--src", str(src),
                    "--out-txt", str(out_txt),
                    "--out-pdf", str(out_pdf),
                    "--dpi", str(args.dpi),
                ],
                env={
                    **__import__("os").environ,
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                },
                timeout=timeout_s,
                check=False,
            )
            elapsed = time.time() - t0
            if res.returncode == 0 and cached(src):
                print(f"   done in {elapsed:.0f}s", flush=True)
            else:
                msg = f"exit {res.returncode}"
                print(f"   FAILED: {msg}", flush=True)
                append_failed(src.name, msg)
                # Clean partial outputs so re-runs retry from scratch.
                for p in (out_txt, out_pdf):
                    if p.exists() and p.stat().st_size < 1024:
                        p.unlink()
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            print(f"   TIMEOUT after {elapsed:.0f}s — killed, skipping.", flush=True)
            append_failed(src.name, f"timeout after {args.per_file_timeout_min} min")
            for p in (out_txt, out_pdf):
                if p.exists() and p.stat().st_size < 1024:
                    p.unlink()

    print("\nALL_DONE", flush=True)


if __name__ == "__main__":
    main()
