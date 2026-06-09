"""Scan the new Drive batch — classify each file as clean-text PDF / scanned PDF / DOCX.

For each PDF: get page count, check if it has extractable text on a sample of pages.
For each DOCX: get extracted text length.
Output a CSV-ish report so we can decide what to ingest, dedupe, and categorize.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

SRC = Path("C:/Users/LENOVO/Desktop/drive-download-20260605T125440Z-3-001")
OUT = Path("C:/Users/LENOVO/Desktop/AI Law/data/new_batch_scan.json")


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_pdf(path: Path) -> dict:
    try:
        doc = fitz.open(str(path))
    except Exception as e:
        return {"error": f"open failed: {e}"}
    n = doc.page_count
    # Sample first / middle / last pages to gauge text content
    sample_idx = sorted(set([0, n // 2, n - 1])) if n > 0 else [0]
    text_chars = 0
    sample_text = ""
    for i in sample_idx:
        try:
            t = doc[i].get_text("text") or ""
        except Exception:
            t = ""
        text_chars += len(t.strip())
        if i == 0:
            sample_text = t.strip()[:300]
    doc.close()
    return {
        "pages": n,
        "sample_text_chars": text_chars,
        "first_page_snippet": sample_text,
        "is_clean_text": text_chars > 100,  # threshold for "has real text"
    }


def scan_docx(path: Path) -> dict:
    try:
        import docx  # python-docx
    except ImportError:
        return {"error": "python-docx not installed"}
    try:
        d = docx.Document(str(path))
    except Exception as e:
        return {"error": f"open failed: {e}"}
    text_parts = [p.text for p in d.paragraphs if p.text.strip()]
    text = "\n".join(text_parts)
    return {
        "paragraphs": len(text_parts),
        "text_chars": len(text),
        "first_300": text[:300],
        "is_clean_text": len(text) > 100,
    }


def main():
    files = sorted(SRC.iterdir())
    out: list[dict] = []
    for p in files:
        if not p.is_file():
            continue
        rec: dict = {"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1)}
        if p.suffix.lower() == ".pdf":
            rec["type"] = "pdf"
            rec["md5"] = md5(p)
            rec.update(scan_pdf(p))
        elif p.suffix.lower() in (".docx", ".doc"):
            rec["type"] = "docx"
            rec["md5"] = md5(p)
            rec.update(scan_docx(p))
        else:
            rec["type"] = "other"
        out.append(rec)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # Console summary
    pdfs = [r for r in out if r["type"] == "pdf"]
    docxs = [r for r in out if r["type"] == "docx"]
    clean = [r for r in pdfs if r.get("is_clean_text")]
    scanned = [r for r in pdfs if not r.get("is_clean_text")]
    print(f"Total: {len(out)} | PDFs: {len(pdfs)} | DOCX: {len(docxs)}")
    print(f"  Clean-text PDFs: {len(clean)}")
    print(f"  Scanned PDFs:    {len(scanned)}")

    # Duplicates by MD5
    by_md5: dict[str, list[str]] = {}
    for r in out:
        if "md5" in r:
            by_md5.setdefault(r["md5"], []).append(r["name"])
    dupes = {k: v for k, v in by_md5.items() if len(v) > 1}
    if dupes:
        print(f"\nDuplicate sets ({len(dupes)}):")
        for k, names in dupes.items():
            print(f"  {k[:8]} → {', '.join(names)}")
    else:
        print("\nNo md5-identical duplicates.")

    if scanned:
        print(f"\nScanned PDFs (will be set aside):")
        for r in scanned:
            print(f"  - {r['name']} ({r['pages']}p, only {r['sample_text_chars']} chars)")


if __name__ == "__main__":
    main()
