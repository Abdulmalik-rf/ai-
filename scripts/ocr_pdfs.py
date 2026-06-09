"""OCR each PDF in data/drive_raw/ that lacks clean embedded text.

Outputs:
  data/ocr_text/<stem>.txt  — plain OCR text, page-marked, used for
                              classification and as a fallback chunker source.
  data/ocr_pdf/<file>.pdf   — rebuilt PDF: original page raster + invisible
                              searchable text overlay. Preserves the original
                              look of scanned legal documents (signatures,
                              MoJ letterheads, decree stamps) so when the user
                              clicks a citation in the dashboard they see the
                              real document, not synthesized text.

Tuned for full-fidelity legal-document use:
  - DPI 200 (default) — sharp enough for printed Arabic, ~2x faster than 300.
  - Parallel-safe via --shard N/M (md5 hash bucketing, no two shards touch
    the same file).
  - Resumable: if BOTH outputs exist for a file, it's skipped on re-run.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sys
import time
import unicodedata
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "drive_raw"
OUT_TEXT = ROOT / "data" / "ocr_text"
OUT_PDF = ROOT / "data" / "ocr_pdf"
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
        if not non_ws:
            return False
        arabic = sum(1 for c in text if "؀" <= c <= "ۿ")
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 0x0250)
        if (arabic + latin) / non_ws < 0.3:
            return False
        hits = sum(1 for w in _PROBE if w in text)
        return hits >= 3
    except Exception:  # noqa: BLE001
        return False


def render_page(page: "fitz.Page", dpi: int) -> Image.Image:
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def shard_match(name: str, shard_index: int, shard_count: int) -> bool:
    if shard_count <= 1:
        return True
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    return (h % shard_count) == shard_index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--re-do", action="store_true",
                        help="Re-OCR even if cached outputs exist.")
    parser.add_argument("--force", action="store_true",
                        help="OCR even if the source PDF already has clean text.")
    parser.add_argument("--files", nargs="*", default=None)
    parser.add_argument("--shard", type=str, default="0/1",
                        help="N/M — only files whose md5 % M == N. 0/1 = all.")
    args = parser.parse_args()

    shard_idx, shard_cnt = (int(x) for x in args.shard.split("/"))

    import easyocr
    print(f"[shard {shard_idx}/{shard_cnt}] loading easyocr (dpi={args.dpi}, gpu={args.gpu})…", flush=True)
    reader = easyocr.Reader(["ar", "en"], gpu=args.gpu, verbose=False)

    all_pdfs = sorted(RAW.glob("*.pdf"))
    if args.files:
        wanted = {unicodedata.normalize("NFC", n) for n in args.files}
        targets = [p for p in all_pdfs if unicodedata.normalize("NFC", p.name) in wanted]
        force_all = True
    else:
        targets = all_pdfs
        force_all = args.force

    todo: list[Path] = []
    for p in targets:
        if not shard_match(p.name, shard_idx, shard_cnt):
            continue
        out_txt = OUT_TEXT / (p.stem + ".txt")
        out_pdf = OUT_PDF / p.name
        cached = (
            not args.re_do
            and out_txt.exists() and out_txt.stat().st_size > 50
            and out_pdf.exists() and out_pdf.stat().st_size > 1024
        )
        if cached:
            continue
        if not force_all and has_clean_text(p):
            continue
        todo.append(p)

    print(f"[shard {shard_idx}/{shard_cnt}] {len(todo)} files to OCR.\n", flush=True)

    for idx, src in enumerate(todo, 1):
        out_txt = OUT_TEXT / (src.stem + ".txt")
        out_pdf = OUT_PDF / src.name

        t0 = time.time()
        full_text_parts: list[str] = []
        new_doc = fitz.open()
        try:
            with fitz.open(str(src)) as doc:
                n_pages = len(doc)
                print(f"[shard {shard_idx}] [{idx}/{len(todo)}] {src.name} ({n_pages}p) …", flush=True)
                for pno, page in enumerate(doc, 1):
                    img = render_page(page, dpi=args.dpi)
                    arr = np.array(img)
                    result = reader.readtext(arr, detail=1, paragraph=False)
                    page_lines = [t.strip() for _, t, _ in result if t and t.strip()]
                    page_str = "\n".join(page_lines)
                    full_text_parts.append(f"--- Page {pno} ---\n{page_str}\n")

                    # Rebuilt PDF page: same dimensions as source, with the
                    # rasterized image as the visible layer + invisible OCR
                    # text overlaid so search/copy works.
                    new_page = new_doc.new_page(
                        width=page.rect.width, height=page.rect.height
                    )
                    png = io.BytesIO()
                    img.save(png, format="PNG")
                    new_page.insert_image(new_page.rect, stream=png.getvalue())
                    if page_str.strip():
                        # tiny font, white color = invisible against any bg;
                        # PDF parsers still extract it as real text.
                        new_page.insert_text(
                            (10, 10), page_str, fontsize=1,
                            color=(1, 1, 1), overlay=True,
                        )
            new_doc.save(str(out_pdf), deflate=True)
            new_doc.close()
            out_txt.write_text("\n".join(full_text_parts), encoding="utf-8")
            elapsed = time.time() - t0
            chars = sum(len(p) for p in full_text_parts)
            size_mb = out_pdf.stat().st_size / 1e6
            print(f"    -> {n_pages}p, {chars} chars, PDF {size_mb:.1f} MB, {elapsed:.0f}s", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"    !! FAILED: {exc!r}", flush=True)
            if full_text_parts:
                out_txt.write_text("\n".join(full_text_parts), encoding="utf-8")
            try:
                new_doc.close()
            except Exception:  # noqa: BLE001
                pass

    print(f"\n[shard {shard_idx}/{shard_cnt}] ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
