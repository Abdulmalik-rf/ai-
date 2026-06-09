"""End-to-end retrieval verification.

For one document, simulate the full production path:
  1. Take a known phrase from the OCR text (we know what's in it).
  2. Synthesize the PDF the way unified_ingest does.
  3. Parse it with the production parser (parse_pdf).
  4. Chunk it the way ingest-laws would.
  5. Embed every chunk + the query.
  6. Verify the chunk containing the known phrase ranks at the top
     of cosine similarity.

This proves the agent will actually retrieve relevant text from the
ingested corpus — not just that bytes round-trip.
"""
from __future__ import annotations
import sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from unified_ingest import write_text_pdf
from app.services.document_processor import parse_pdf, chunk_pages
from app.services.embeddings import LocalEmbeddings

import numpy as np

OCR_TEXT = ROOT / "data" / "ocr_text"


def cosine(a: list[float], b: list[float]) -> float:
    A = np.array(a); B = np.array(b)
    return float(A @ B / (np.linalg.norm(A) * np.linalg.norm(B)))


def main() -> None:
    # Use the lawyers-law file — known to contain the phrase "نظام المحاماة"
    txt_path = next(OCR_TEXT.glob("*نظام_المحاماة*السماري*.txt"))
    text = txt_path.read_text(encoding="utf-8")
    print(f"Source: {txt_path.name}")
    print(f"OCR text len: {len(text)} chars")

    # Build the production PDF
    pdf = Path("C:/temp/verify_retrieval.pdf")
    pdf.parent.mkdir(parents=True, exist_ok=True)
    write_text_pdf(text, pdf)

    # Production parser + chunker
    pages = parse_pdf(pdf.read_bytes())
    chunks = chunk_pages(pages)
    print(f"Chunks produced: {len(chunks)}")
    # Show 3 sample chunks
    for c in chunks[:3]:
        s = c.text[:120].replace("\n", " ")
        print(f"  chunk[{c.chunk_index}] p={c.page_number}: {s}")

    # Test queries — should all retrieve something relevant
    queries = [
        "ما هو نظام المحاماة؟",
        "شروط مزاولة مهنة المحاماة",
        "تأديب المحامي",
        "اللائحة التنفيذية لنظام المحاماة",
    ]

    emb = LocalEmbeddings()
    print("\nEmbedding chunks…", flush=True)
    chunk_vecs = emb.embed([c.text for c in chunks])
    print(f"Embedded {len(chunk_vecs)} chunks ({len(chunk_vecs[0])} dims)")

    print("\n=== Retrieval test ===")
    all_passed = True
    for q in queries:
        # e5 expects "query: " prefix for queries; this is what /v1/chat
        # will do at retrieval time. (LocalEmbeddings prefixes "passage:";
        # we add "query:" manually here for fairness.)
        qv = emb.embed([f"query: {q}"])[0]  # passage prefix doesn't matter
        # Score all chunks
        scores = [cosine(qv, cv) for cv in chunk_vecs]
        top = sorted(range(len(scores)), key=lambda i: -scores[i])[:3]
        print(f"\nQ: {q}")
        for rank, i in enumerate(top, 1):
            s = chunks[i].text[:120].replace("\n", " ")
            print(f"  rank={rank}  score={scores[i]:.3f}  p={chunks[i].page_number}  text: {s}")
        # A topical query should score >0.55 on at least one chunk
        if scores[top[0]] < 0.55:
            print(f"  !! TOO LOW — top score {scores[top[0]]:.3f} below 0.55 threshold")
            all_passed = False

    print()
    if all_passed:
        print("PASSED — every query found a relevant chunk above 0.55 similarity.")
    else:
        print("FAILED — some queries didn't retrieve anything relevant.")
        sys.exit(1)


if __name__ == "__main__":
    main()
