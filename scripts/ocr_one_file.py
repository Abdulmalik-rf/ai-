"""OCR a single PDF — used by ocr_pdfs_resilient.py as a subprocess so a
parent watcher can apply per-file timeouts (Windows can't SIGALRM).

Exits 0 on success. The parent kills us if we exceed its timeout.
"""
from __future__ import annotations
import argparse
import io
import sys
import time
from pathlib import Path

import fitz
import numpy as np
from PIL import Image


def render_page(page: "fitz.Page", dpi: int) -> Image.Image:
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--out-txt", type=Path, required=True)
    parser.add_argument("--out-pdf", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    import easyocr
    reader = easyocr.Reader(["ar", "en"], gpu=False, verbose=False)

    full_text_parts: list[str] = []
    new_doc = fitz.open()
    t0 = time.time()
    with fitz.open(str(args.src)) as doc:
        n_pages = len(doc)
        print(f"  OCR start: {args.src.name} ({n_pages}p)", flush=True)
        for pno, page in enumerate(doc, 1):
            img = render_page(page, dpi=args.dpi)
            arr = np.array(img)
            result = reader.readtext(arr, detail=1, paragraph=False)
            page_lines = [t.strip() for _, t, _ in result if t and t.strip()]
            page_str = "\n".join(page_lines)
            full_text_parts.append(f"--- Page {pno} ---\n{page_str}\n")

            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            png = io.BytesIO()
            img.save(png, format="PNG")
            new_page.insert_image(new_page.rect, stream=png.getvalue())
            if page_str.strip():
                new_page.insert_text(
                    (10, 10), page_str, fontsize=1, color=(1, 1, 1), overlay=True
                )
            print(f"    page {pno}/{n_pages} (+{time.time()-t0:.0f}s)", flush=True)

    new_doc.save(str(args.out_pdf), deflate=True)
    new_doc.close()
    args.out_txt.write_text("\n".join(full_text_parts), encoding="utf-8")
    elapsed = time.time() - t0
    chars = sum(len(p) for p in full_text_parts)
    size_mb = args.out_pdf.stat().st_size / 1e6
    print(f"  OK: {n_pages}p, {chars} chars, {size_mb:.1f} MB, {elapsed:.0f}s", flush=True)


if __name__ == "__main__":
    main()
