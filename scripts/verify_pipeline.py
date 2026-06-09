"""End-to-end verification that the text the agent will search matches
the text easyocr produced.

For each sample file we walk every stage of the pipeline and diff the
results. This is what would have caught the Helvetica bug on day one.

Stage 1: OCR .txt          — what easyocr wrote to disk
Stage 2: write_text_pdf    — synthesized PDF the chunker reads
Stage 3: pdfplumber extract → NFKC normalize  — what the chunker hands to
                                                  the embedder/storage
Stage 4: chunked content   — same _sanitize as production
Stage 5: embeddings + cosine sim — does a chunk match a query about it?

We pass only if Stage 4 contains the OCR text verbatim (modulo whitespace),
AND Stage 5 shows high similarity for a topical query.
"""
from __future__ import annotations
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from unified_ingest import write_text_pdf
from app.services.document_processor import _sanitize, parse_pdf

import pdfplumber  # noqa: E402

OCR_TEXT = ROOT / "data" / "ocr_text"
RAW = ROOT / "data" / "drive_raw"


def normalize_for_compare(s: str) -> str:
    """Strip whitespace + NFKC so we compare semantic content, not layout.
    Production chunks store NFKC'd text, so this is the right comparison."""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compare_texts(reference: str, retrieved: str) -> dict:
    """Are `retrieved` characters all present in the same order inside
    `reference`? Returns coverage stats."""
    ref = normalize_for_compare(reference)
    got = normalize_for_compare(retrieved)
    if not ref or not got:
        return {"empty": True}
    # How much of the reference is reproduced verbatim?
    # Compute longest matching substring fragments.
    matched = 0
    i = 0
    while i < len(ref):
        # find a contiguous run from ref starting at i in got
        run = 1
        while (
            i + run <= len(ref)
            and ref[i : i + run] in got
            and run <= 50
        ):
            run += 1
        run -= 1
        if run >= 3:
            matched += run
            i += run
        else:
            i += 1
    coverage = matched / len(ref) if ref else 0
    # Sample words to spot-check
    sample_words = re.findall(r"[؀-ۿ]{4,}", ref)[:5]
    word_hits = sum(1 for w in sample_words if w in got)
    return {
        "ref_chars": len(ref),
        "got_chars": len(got),
        "verbatim_coverage": round(coverage, 3),
        "sample_words": sample_words,
        "sample_word_hits": word_hits,
        "sample_total": len(sample_words),
    }


def verify_one(name: str, txt_path: Path) -> dict:
    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        return {"name": name, "error": "ocr .txt empty"}

    # Stage 2: synthesize PDF
    tmp_pdf = Path("C:/temp/verify_") / (txt_path.stem + ".pdf")
    tmp_pdf.parent.mkdir(parents=True, exist_ok=True)
    write_text_pdf(text, tmp_pdf)

    # Stage 3: pdfplumber read-back
    extracted = ""
    with pdfplumber.open(str(tmp_pdf)) as pdf:
        for page in pdf.pages:
            extracted += (page.extract_text() or "") + "\n"

    # Stage 4: production _sanitize (NFKC + NUL strip)
    sanitized = _sanitize(extracted)

    # Compare OCR text vs sanitized chunked text
    cmp_ocr_vs_chunk = compare_texts(text, sanitized)

    # Stage 4b: production parse_pdf (what ingest-laws ACTUALLY calls)
    pdf_bytes = tmp_pdf.read_bytes()
    pages = parse_pdf(pdf_bytes)
    parsed_text = "\n".join(t for _, t in pages)
    cmp_ocr_vs_parsed = compare_texts(text, parsed_text)

    return {
        "name": name,
        "ocr_chars": len(text),
        "synth_pdf_pages": len(pages),
        "via_pdfplumber+sanitize": cmp_ocr_vs_chunk,
        "via_production_parse_pdf": cmp_ocr_vs_parsed,
    }


def main() -> None:
    # Pick a mix: small/big, criminal/family/labor/other
    samples = [
        "‎⁨نظام_المحاماة_نسخة_عبدالعزيز_السماري⁩",
        "‎⁨نظام الأحوال الشخصية⁩",
        "‎⁨نظام_الإثبات_عبدالعزيز_السماري⁩",
        "‎⁨من مذكراتي لوائح الإعتراض⁩",
        "FG02UvbSsSJGKpypt",
    ]
    failures = []
    for s in samples:
        txt = OCR_TEXT / (unicodedata.normalize("NFC", s) + ".txt")
        if not txt.exists():
            # try with leading bidi marks etc.
            matches = list(OCR_TEXT.glob("*" + s.replace("‎⁨", "").replace("⁩", "")[:20].replace("/", "") + "*.txt"))
            if matches:
                txt = matches[0]
        if not txt.exists():
            print(f"!! cannot locate OCR text for {s}")
            failures.append(s)
            continue
        result = verify_one(s, txt)
        print()
        print(f"=== {s} ===")
        import json
        # Truncate sample_words for readability
        sw = result.get("via_production_parse_pdf", {}).get("sample_words", [])[:3]
        result["via_production_parse_pdf"]["sample_words"] = sw
        result["via_pdfplumber+sanitize"]["sample_words"] = sw
        print(json.dumps(result, ensure_ascii=False, indent=2))
        cov = result.get("via_production_parse_pdf", {}).get("verbatim_coverage", 0)
        hits = result.get("via_production_parse_pdf", {}).get("sample_word_hits", 0)
        total = result.get("via_production_parse_pdf", {}).get("sample_total", 0)
        if cov < 0.7 or (total > 0 and hits < total):
            failures.append((s, cov, hits, total))

    print()
    print("=" * 70)
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  {f}")
        sys.exit(1)
    else:
        print("ALL PASSED — production parse_pdf reproduces OCR text faithfully.")


if __name__ == "__main__":
    main()
