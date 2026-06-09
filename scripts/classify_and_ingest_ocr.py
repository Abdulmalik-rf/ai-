"""After OCR finishes, auto-classify each OCR'd PDF by Arabic keyword scan
of its OCR text, copy to data/corpus_ocr/<domain>/<descriptive>.pdf, then
run ingest-laws per domain.

Domain keyword rules mirror app.services.rag._DOMAIN_KEYWORDS but include a
few extras for procedural / criminal / IP that the original keyword
classifier covers via different routes.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OCR_PDF = ROOT / "data" / "ocr_pdf"
OCR_TEXT = ROOT / "data" / "ocr_text"
CORPUS_OCR = ROOT / "data" / "corpus_ocr"

VENV_PY = ROOT / "apps" / "api" / ".venv" / "Scripts" / "python.exe"


# Keyword bundles per domain (Arabic + English). The classifier picks the
# domain with the highest hit count; ties go to "other".
KEYWORDS: dict[str, list[str]] = {
    "labor": [
        "نظام العمل", "عقد عمل", "عامل", "صاحب العمل", "أجر", "راتب",
        "إجازة", "ساعات العمل", "إنهاء عقد", "مكافأة نهاية الخدمة",
        "labor", "labour", "employment",
    ],
    "commercial": [
        "السجل التجاري", "تاجر", "عقود تجارية", "محكمة تجارية", "إفلاس",
        "منافسة", "commercial", "trade", "merchant",
    ],
    "family": [
        "الأحوال الشخصية", "زواج", "طلاق", "نفقة", "حضانة", "ميراث",
        "family", "marriage", "divorce",
    ],
    "criminal": [
        "نظام الإجراءات الجزائية", "جزائي", "جريمة", "عقوبة", "سجن",
        "الادعاء العام", "النيابة", "criminal", "penal",
    ],
    "real_estate": [
        "العقار", "ملكية عقارية", "إيجار", "تطوير عقاري", "real estate",
        "property", "lease",
    ],
    "ip": [
        "براءة اختراع", "العلامة التجارية", "حقوق المؤلف", "ملكية فكرية",
        "patent", "trademark", "copyright",
    ],
    "corporate": [
        "نظام الشركات", "شركة مساهمة", "شركة ذات مسؤولية", "حوكمة",
        "مجلس إدارة", "تأسيس شركة", "corporate", "joint stock",
    ],
    "banking": [
        "البنك", "البنك المركزي", "ساما", "تمويل", "قرض", "مرابحة",
        "banking", "bank", "finance",
    ],
    "administrative": [
        "ديوان المظالم", "إداري", "عقد إداري", "موظف عام",
        "administrative", "diwan",
    ],
}


def classify(text: str) -> str:
    if not text:
        return "other"
    counts: Counter[str] = Counter()
    low = text.lower()
    for domain, kws in KEYWORDS.items():
        for kw in kws:
            counts[domain] += low.count(kw.lower())
    if not counts:
        return "other"
    domain, count = counts.most_common(1)[0]
    return domain if count >= 2 else "other"


def title_from_text(text: str, fallback: str) -> str:
    """Pick the first plausible Arabic title line — short, no junk."""
    if not text:
        return fallback
    # Strip obvious page markers
    text = re.sub(r"---\s*Page\s*\d+\s*---", "", text)
    for line in text.splitlines():
        s = line.strip()
        # Drop short, noisy, or numeric-only lines.
        if 8 <= len(s) <= 120 and re.search(r"[؀-ۿ]", s):
            # Avoid lines that are mostly punctuation/digits
            non_ws = sum(1 for c in s if not c.isspace())
            arabic = sum(1 for c in s if "؀" <= c <= "ۿ")
            if non_ws and arabic / non_ws > 0.5:
                # Sanitize for filesystem.
                s = re.sub(r"[\\/:*?\"<>|]", "-", s)
                return s
    return fallback


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if CORPUS_OCR.exists():
        shutil.rmtree(CORPUS_OCR)
    CORPUS_OCR.mkdir(parents=True)

    pdfs = sorted(OCR_PDF.glob("*.pdf"))
    plan: list[tuple[Path, str, str]] = []  # (src, domain, target_name)
    for pdf in pdfs:
        txt_path = OCR_TEXT / (pdf.stem + ".txt")
        if not txt_path.exists():
            print(f"[skip] no .txt for {pdf.name}", flush=True)
            continue
        text = txt_path.read_text(encoding="utf-8", errors="ignore")
        domain = classify(text)
        title = title_from_text(text, fallback=f"وثيقة قضائية ({pdf.stem})")
        target_name = f"{title}.pdf"
        plan.append((pdf, domain, target_name))

    by_domain: dict[str, int] = Counter()
    for src, domain, target_name in plan:
        by_domain[domain] += 1
        dom_dir = CORPUS_OCR / domain
        dom_dir.mkdir(exist_ok=True)
        dst = dom_dir / unicodedata.normalize("NFC", target_name)
        # If duplicate title, append the original stem.
        if dst.exists():
            dst = dom_dir / f"{dst.stem} - {src.stem}.pdf"
        if not args.dry_run:
            shutil.copy2(src, dst)

    print("Domain plan:")
    for d, n in sorted(by_domain.items(), key=lambda kv: -kv[1]):
        print(f"  {d}: {n} files")
    for src, domain, target_name in plan:
        print(f"  {domain}: {target_name}  <- {src.name}")

    if args.dry_run:
        return

    print("\n=== Running ingest-laws per domain ===")
    for domain in sorted(by_domain):
        dom_dir = CORPUS_OCR / domain
        if not any(dom_dir.iterdir()):
            continue
        print(f"\n--- {domain} ({by_domain[domain]} files) ---", flush=True)
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        cmd = [
            str(VENV_PY), "-m", "app.cli", "ingest-laws",
            str(dom_dir),
            "--domain", domain,
            "--language", "ar",
            "--tenant", "platform",
            "--authority", "Saudi Ministry of Justice",
        ]
        # Run from the apps/api dir so .env loads properly.
        subprocess.run(
            cmd,
            cwd=str(ROOT / "apps" / "api"),
            env={**__import__("os").environ, **env},
            check=False,
        )


if __name__ == "__main__":
    main()
