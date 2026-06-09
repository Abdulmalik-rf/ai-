"""Unified, idempotent ingestion of every PDF in data/drive_raw/.

For each source PDF, picks the best text source:
  - The original PDF if its embedded text is clean Arabic/English.
  - Otherwise, the OCR'd version under data/ocr_pdf/<same-name>.pdf.

Files lacking both clean text AND OCR are reported as "missing" — the script
exits non-zero so the caller knows the corpus is incomplete.

Each file:
  - Gets a content-derived legal domain via Arabic/English keyword hits.
  - Gets a descriptive title taken from the first plausible line of text.
  - Lands at data/corpus_final/<domain>/<title>.pdf.

After staging, the script wipes existing platform-tenant documents and re-runs
`app.cli ingest-laws` once per non-empty domain folder. At the end it asserts
the document count in DB equals the count of staged files.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "drive_raw"
OCR_PDF = ROOT / "data" / "ocr_pdf"  # legacy — older runs wrote rebuilt PDFs here
OCR_TEXT = ROOT / "data" / "ocr_text"  # current — OCR-only-text outputs
CORPUS = ROOT / "data" / "corpus_final"

VENV_PY = ROOT / "apps" / "api" / ".venv" / "Scripts" / "python.exe"
API_DIR = ROOT / "apps" / "api"

# Keyword bundles per domain. Each phrase is matched as a plain substring,
# so all entries should be unambiguous, multi-word, or domain-specific
# enough that they don't collide with words in other domains.
# Each phrase is given a weight: high-precision phrases are worth more
# than generic ones.
DOMAINS: list[tuple[str, list[tuple[str, int]]]] = [
    ("ip", [
        ("ملكية فكرية", 4), ("الملكية الفكرية", 4),
        ("براءة اختراع", 4), ("براءات الاختراع", 4),
        ("العلامة التجارية", 3), ("العلامات التجارية", 3),
        ("حقوق المؤلف", 3), ("intellectual property", 3),
        ("patent", 2), ("trademark", 2), ("copyright", 2),
    ]),
    ("labor", [
        ("نظام العمل", 4), ("عقد عمل", 3), ("عقود العمل", 3),
        ("صاحب العمل", 3), ("ساعات العمل", 3),
        ("مكافأة نهاية الخدمة", 4), ("إنهاء عقد العمل", 4),
        ("فصل تعسفي", 3),
        ("employment contract", 2), ("labor law", 3), ("labour law", 3),
    ]),
    ("commercial", [
        ("السجل التجاري", 4), ("نظام المحكمة التجارية", 4),
        ("نظام الشركات التجارية", 3), ("العقود التجارية", 3),
        ("نظام الإفلاس", 4), ("نظام المنافسة", 4),
        ("commercial court", 3), ("bankruptcy", 2),
    ]),
    ("family", [
        ("الأحوال الشخصية", 4), ("نظام الأحوال الشخصية", 4),
        ("الطلاق", 2), ("الحضانة", 3), ("النفقة", 2), ("الميراث", 2),
        ("personal status", 3), ("custody", 2), ("alimony", 2),
    ]),
    ("criminal", [
        ("نظام الإجراءات الجزائية", 4), ("القاضي الجزائي", 4),
        ("المحكمة الجزائية", 4), ("النيابة العامة", 3),
        ("جريمة", 2), ("عقوبة", 2), ("التعزير", 3), ("القصاص", 3),
        ("criminal law", 3), ("criminal procedure", 3),
    ]),
    ("real_estate", [
        ("نظام التسجيل العيني", 4), ("التطوير العقاري", 3),
        ("الملكية العقارية", 4), ("إيجار العقار", 3),
        ("real estate", 3), ("property law", 3),
    ]),
    ("corporate", [
        ("نظام الشركات", 4), ("شركة مساهمة", 3),
        ("الشركات المساهمة", 3), ("شركة ذات مسؤولية محدودة", 4),
        ("حوكمة الشركات", 4), ("مجلس الإدارة", 3),
        ("joint stock", 2), ("llc", 1), ("corporate governance", 3),
    ]),
    ("banking", [
        ("البنك المركزي", 3), ("مؤسسة النقد", 3), ("ساما", 2),
        ("نظام مراقبة البنوك", 4), ("التمويل المصرفي", 3), ("المرابحة", 2),
        ("الصكوك", 2),
        ("central bank", 3), ("banking law", 3), ("islamic finance", 3),
    ]),
    ("administrative", [
        ("ديوان المظالم", 4), ("القضاء الإداري", 4),
        ("نظام الخدمة المدنية", 4), ("الموظف العام", 3),
        ("اللائحة التنفيذية للخدمة المدنية", 4),
        ("administrative court", 3), ("public servant", 2),
    ]),
]


# Common Arabic stop-words / structural terms. Real-Arabic PDFs hit several
# of these in the first pages; CID-garbled or font-encoded PDFs hit zero.
_ARABIC_PROBE_WORDS = (
    "في ", "من ", "إلى", "على", "عن ", "كان", "هذا", "هذه",
    "مادة", "نظام", "محكمة", "قضاء", "حكم", "قانون", "وزارة", "المملكة",
)
_ARABIC_PROBE_THRESHOLD = 3


def has_clean_text(path: Path, sample_pages: int = 6) -> bool:
    """The embedded text layer must extract ≥600 chars and contain ≥3 real
    Arabic stop-words. CID/glyph-encoded PDFs map bytes to Arabic codepoints
    but spell nothing real, so the stop-word hit count is 0–1.
    """
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
        hits = sum(1 for w in _ARABIC_PROBE_WORDS if w in text)
        return hits >= _ARABIC_PROBE_THRESHOLD
    except Exception:  # noqa: BLE001
        return False


def get_text(path: Path, max_chars: int = 12000) -> str:
    """Concatenate text from the first ~12 pages of `path`."""
    try:
        with fitz.open(str(path)) as doc:
            text = ""
            for i, page in enumerate(doc):
                if i >= 12:
                    break
                text += page.get_text("text") or "\n"
                if len(text) > max_chars:
                    break
        return text
    except Exception:  # noqa: BLE001
        return ""


def get_ocr_text(stem: str) -> str:
    p = OCR_TEXT / f"{stem}.txt"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")
    return ""


def classify(text: str) -> str:
    """Score each domain by counting weighted keyword hits in the document
    text and return the highest-scoring domain (or "other" when nothing
    crosses a small min-score threshold).
    """
    if not text:
        return "other"
    low = text.lower()
    scores: Counter[str] = Counter()
    for domain, weighted in DOMAINS:
        for kw, weight in weighted:
            scores[domain] += low.count(kw.lower()) * weight
    if not scores:
        return "other"
    domain, score = scores.most_common(1)[0]
    return domain if score >= 4 else "other"


def normalize_filename(s: str) -> str:
    """Strip filesystem-hostile chars and Unicode-normalize."""
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[\\/:*?\"<>|]", "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Trim trailing dots/spaces (Windows)
    s = s.rstrip(". ")
    # Cap length so the full path stays under MAX_PATH
    if len(s) > 110:
        s = s[:110].rstrip()
    return s


def title_from_text(text: str, fallback: str) -> str:
    if not text:
        return fallback
    # Remove page markers that the OCR script inserts.
    cleaned = re.sub(r"---\s*Page\s*\d+\s*---", "", text)
    for raw in cleaned.splitlines():
        s = raw.strip()
        if not (8 <= len(s) <= 140):
            continue
        if not re.search(r"[؀-ۿ]", s):
            continue
        non_ws = sum(1 for c in s if not c.isspace())
        arabic = sum(1 for c in s if "؀" <= c <= "ۿ")
        if non_ws and arabic / non_ws < 0.4:
            continue
        # Drop lines that are URLs / phone-y noise
        if re.search(r"https?://|@|qadha\.org|9665|0096", s):
            continue
        return normalize_filename(s)
    return fallback


def descriptive_filename(stem_fallback: str, text: str, src: Path) -> str:
    title = title_from_text(text, fallback="")
    if title:
        return f"{title}.pdf"
    # Fall back to the source filename (already-named files keep their names).
    base = unicodedata.normalize("NFC", src.stem)
    if re.search(r"[؀-ۿ]", base):
        return f"{normalize_filename(base)}.pdf"
    return f"وثيقة قضائية ({stem_fallback}).pdf"


_ARABIC_FONT = "C:/Windows/Fonts/arial.ttf"


def write_text_pdf(text: str, target: Path) -> None:
    """Write OCR text into a lightweight text-only PDF.

    Critical: must use an Arabic-capable font (arial.ttf) — Helvetica has no
    Arabic glyphs, so writing "نظام" with `fontname="helv"` silently turns
    every character into a `·` placeholder that pdfplumber later extracts as
    dots, breaking the chunker. With arial.ttf the text round-trips as
    Arabic Presentation Forms, and our document_processor._sanitize NFKC's
    them back to canonical base letters.

    Pages are 595×842pt (A4); text flows page-by-page so very long OCR
    transcripts (e.g. the 502-page judgment book) still fit.
    """
    doc = fitz.open()
    margin = 36
    width, height = 595, 842
    rect = fitz.Rect(margin, margin, width - margin, height - margin)

    # `insert_textbox` is binary: if the requested text would overflow the
    # rect, it inserts NOTHING and returns a negative value. So we shrink the
    # slice in halves until the call succeeds.
    pos = 0
    safety = 0
    while pos < len(text) and safety < 10000:
        safety += 1
        # Start by trying a generous slice; halve until it fits.
        slice_len = min(2000, len(text) - pos)
        while slice_len > 0:
            page = doc.new_page(width=width, height=height)
            page.insert_font(fontname="AR", fontfile=_ARABIC_FONT)
            ret = page.insert_textbox(
                rect, text[pos : pos + slice_len],
                fontsize=10, fontname="AR", align=0,
            )
            if ret >= 0:
                pos += slice_len
                break
            # Overflow — drop the page and try a smaller slice.
            doc.delete_page(len(doc) - 1)
            slice_len //= 2
        if slice_len == 0:
            # Single char wouldn't fit — should never happen at 10pt on A4.
            # Advance one char to avoid an infinite loop.
            pos += 1
    if len(doc) == 0:
        # Empty input — still write a blank page so the file is valid.
        doc.new_page(width=width, height=height)
    doc.save(str(target), deflate=True)
    doc.close()


def stage_files(clean_only: bool = False) -> tuple[list[tuple[str, Path, str]], list[str]]:
    """Return (placements, missing).

    placements: list of (source_label, target_path, domain)
                source_label = "TXT" (original) or "OCR" (synthesized)
    missing:    list of source filenames with no usable text in either form

    When `clean_only=True`, files that need OCR are not staged — the corpus
    is restricted to PDFs whose embedded text is already canonical Arabic.
    Use this when you'd rather have 95 perfect docs than 196 noisy ones.
    """
    if CORPUS.exists():
        shutil.rmtree(CORPUS)
    CORPUS.mkdir(parents=True)

    placements: list[tuple[str, Path, str]] = []
    missing: list[str] = []
    skipped_ocr: list[str] = []
    used_targets: set[str] = set()

    for src in sorted(RAW.glob("*.pdf")):
        chosen_pdf: Path | None = None
        synth_text: str | None = None

        if has_clean_text(src):
            chosen_pdf = src
            src_text = get_text(src)
            label = "TXT"  # original PDF, clean text
        else:
            if clean_only:
                # Drop scanned/garbled documents entirely.
                skipped_ocr.append(src.name)
                continue
            # Scanned or garbled. Synthesize a text PDF from the OCR .txt —
            # the rebuilt OCR PDF (image + helv-font text overlay) is
            # unsearchable: helvetica has no Arabic glyphs so every Arabic
            # character round-trips as `·`. Lawyers can still view the
            # original scan in data/ocr_pdf/ if needed.
            ocr_txt = get_ocr_text(src.stem)
            if not ocr_txt.strip():
                missing.append(src.name)
                continue
            synth_text = ocr_txt
            src_text = ocr_txt
            label = "OCR"

        domain = classify(src_text)
        target_basename = descriptive_filename(src.stem, src_text, src)
        dom_dir = CORPUS / domain
        dom_dir.mkdir(exist_ok=True)
        target = dom_dir / target_basename

        suffix = 0
        while str(target) in used_targets or target.exists():
            suffix += 1
            target = dom_dir / f"{Path(target_basename).stem} ({suffix}){Path(target_basename).suffix}"
        used_targets.add(str(target))

        if chosen_pdf is not None:
            shutil.copy2(chosen_pdf, target)
        else:
            write_text_pdf(synth_text or "", target)
        placements.append((label, target, domain))

    return placements, missing


def wipe_corpus_db() -> None:
    """Delete every document/chunk in the platform tenant via SQL."""
    cmd = [
        "docker", "exec", "legalai-postgres", "psql", "-U", "legalai",
        "-d", "legalai", "-c",
        "DELETE FROM document_chunks USING documents d WHERE document_chunks.document_id=d.id "
        "AND d.tenant_id=(SELECT id FROM tenants WHERE slug='platform'); "
        "DELETE FROM documents WHERE tenant_id=(SELECT id FROM tenants WHERE slug='platform');",
    ]
    subprocess.run(cmd, check=True)


def docs_in_db() -> int:
    out = subprocess.run(
        [
            "docker", "exec", "legalai-postgres", "psql", "-U", "legalai",
            "-d", "legalai", "-tAc",
            "SELECT COUNT(*) FROM documents WHERE tenant_id=(SELECT id FROM tenants WHERE slug='platform');",
        ],
        capture_output=True, text=True, check=True,
    )
    return int(out.stdout.strip())


def ingest_domain(domain: str, dom_dir: Path) -> None:
    print(f"\n--- ingest-laws --domain {domain} ({sum(1 for _ in dom_dir.iterdir())} files) ---", flush=True)
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        # HF Hub's httpx client closes after a transient error and refuses
        # subsequent requests, killing every file in a batch after the first
        # network hiccup. The sentence-transformers model is already on disk
        # — force offline mode so no HF round-trip happens at all.
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    cmd = [
        str(VENV_PY), "-m", "app.cli", "ingest-laws",
        str(dom_dir),
        "--domain", domain,
        "--language", "ar",
        "--tenant", "platform",
        "--authority", "Saudi Ministry of Justice / Judicial Society",
    ]
    subprocess.run(cmd, cwd=str(API_DIR), env=env, check=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-db", action="store_true",
                        help="Don't wipe the DB before ingesting (incremental mode).")
    parser.add_argument("--allow-missing", action="store_true",
                        help="Proceed even if some source PDFs lack usable text "
                             "(those files are skipped). Useful for partial-corpus "
                             "ingests while heavy OCR retries finish.")
    parser.add_argument("--clean-only", action="store_true",
                        help="Ingest ONLY files whose embedded text is already "
                             "clean Arabic (skip everything that depended on OCR). "
                             "OCR introduces ~5-15%% character noise; this mode "
                             "trades coverage for 100%% verbatim quality.")
    args = parser.parse_args()

    placements, missing = stage_files(clean_only=args.clean_only)

    domain_counts = Counter(d for _, _, d in placements)
    print("=== Stage summary ===")
    for d, n in sorted(domain_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {d}: {n}")
    print(f"  TOTAL: {len(placements)} files staged")
    if missing:
        print(f"\nMISSING ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")

    print("\n=== Placements ===")
    for label, tgt, d in placements:
        print(f"  [{label}] {d:14s} target: {tgt.relative_to(CORPUS)}")

    if args.dry_run:
        return

    if missing and not args.allow_missing:
        print("\nABORT: missing files — run OCR first, or pass --allow-missing.", file=sys.stderr)
        sys.exit(2)

    if not args.keep_db:
        print("\n=== Wiping platform-tenant docs ===")
        wipe_corpus_db()

    print("\n=== Ingesting per domain ===")
    for domain in sorted(domain_counts):
        ingest_domain(domain, CORPUS / domain)

    final = docs_in_db()
    expected = len(placements)
    print(f"\nDocs in DB after ingest: {final} (expected {expected})")
    if missing:
        print(f"({len(missing)} source files skipped because they lack usable text)")
    if final != expected:
        sys.exit(3)
    print("OK — all staged files indexed.")


if __name__ == "__main__":
    main()
