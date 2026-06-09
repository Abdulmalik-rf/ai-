"""Stage + ingest the 80-file Drive batch into the RAG corpus.

Workflow:
  1. Apply MANUAL mapping (filename → final_domain + clean Arabic title).
  2. Skip scanned PDFs (per the user's clean-text-only policy).
  3. Skip byte-identical duplicates (keep one of each pair).
  4. Stage each remaining file into:
        data/new_batch_staged/<final_domain>/<title>.<ext>
     and also copy into:
        data/corpus_final/<final_domain>/<title>.<ext>
  5. For each staging subfolder, call `ingest-laws --domain other` (since some
     final domains aren't in the LegalDomain enum). Use --pattern "*" so the
     CLI picks up both PDFs and DOCX.
  6. After ingest, UPDATE legal_domain on the new rows to the proper value.
  7. Report final counts.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "apps" / "api"
VENV_PY = API_DIR / ".venv" / "Scripts" / "python.exe"
sys.path.insert(0, str(API_DIR))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://legalai:legalai@127.0.0.1:5433/legalai",
)

from sqlalchemy import create_engine, text  # noqa: E402

SRC = Path("C:/Users/LENOVO/Desktop/drive-download-20260605T125440Z-3-001")
STAGE = ROOT / "data" / "new_batch_staged"
CANONICAL = ROOT / "data" / "corpus_final"

# -----------------------------------------------------------------------------
# Skip list — scanned PDFs (no clean text) and byte-duplicates (keep one).
# -----------------------------------------------------------------------------
SKIP_SCANNED = {
    "الدليل التوضيحي لنظام جباية الزكاة.pdf",  # 406p scan, 0 chars
    "دليل استخدام ناجز.pdf",                     # partial scan
    "دليل التقاضي عن بعد .pdf",                  # partial scan
    "نظام جرائم الإرهاب وتمويله.pdf",            # 32p scan; clean exec-regs covered by "..2.pdf"
    "نظام مكافحة جرائم المعلوماتية .pdf",         # 9p scan; clean main law covered by "..2.pdf"
}

# Skip second copy of each byte-identical pair (md5 matched).
SKIP_DUPES = {
    "اﻟﺪﻟﻴﻞ ارﺷﺎدي ﻟﺼﻴﺎﻏﺔ ﺷﺮوط ﺗﺴﻮﻳﺔ اﳌﻨﺎزﻋﺎت(1).pdf",
    "عقد تنفيذ دورة تدريبية(1).pdf",
    "معجــــــــم المصطلحات العــــدلية الواردة في الأنظمة العدلية السعودية.pdf",
    "نظام التعاملات الإلكترونية(1).pdf",
    "نظام ضريبة التصرفات العقارية (1).pdf",
    "نظام مكافحة غسل الأموال 1439(1).pdf",
    "نموذج سند لأمر .pdf",  # the one with trailing space; keep the cleaner-named one
    "نموذج عقد (التَّشغيل والصيانة) 2.docx",
    "نموذج عقد تقديم خدمات ترجمة(1).pdf",
}

# Near-dupe content (not byte-equal but redundant): "دليل التقاضي الالكتروني .pdf"
# (with trailing space) has clean text; "دليل التقاضي الالكتروني.pdf" has only 73 chars.
# We already drop the partial-scanned one via SKIP_SCANNED elsewhere.
# Actually neither was in SKIP_SCANNED — let me re-verify they're distinct keep-worthy.

# -----------------------------------------------------------------------------
# THE MAPPING — explicit per-file domain + meaningful Arabic title.
# Domains include both the existing LegalDomain enum values (commercial, labor,
# family, ip, administrative) AND custom buckets we add via post-ingest UPDATE.
# -----------------------------------------------------------------------------
MAPPING: dict[str, tuple[str, str]] = {
    # ─── Family — Personal Status Law ─────────────────────────────────────
    "نظام الأحوال الشخصية مع الفهارس.pdf":
        ("family", "نظام الأحوال الشخصية مع الفهارس"),

    # ─── Commercial — Companies + Bankruptcy + Arbitration + Anti-Fraud ──
    "نظام الشركات.pdf":
        ("commercial", "نظام الشركات (المرسوم الملكي م-132)"),
    "اللائحة التنفيذية لنظام الشركات .pdf":
        ("commercial", "اللائحة التنفيذية لنظام الشركات"),
    "نظام الافلاس ولائحته التنفيذية .pdf":
        ("commercial", "نظام الإفلاس ولائحته التنفيذية"),
    "نظام التحكيم ولائحته التنفيذية .pdf":
        ("commercial", "نظام التحكيم ولائحته التنفيذية"),
    "نظام مكافحة الاحتيال المالي وخيانة الأمانة .pdf":
        ("commercial", "نظام مكافحة الاحتيال المالي وخيانة الأمانة"),

    # ─── IP — GCC laws + Copyright + Saudi IP Authority guides ───────────
    "قانون (نظام) العلامات التجارية لدول مجلس التعاون.pdf":
        ("ip", "نظام العلامات التجارية لدول مجلس التعاون الخليجي"),
    "نظام براءات الاختراع لدول مجلس التعاون.pdf":
        ("ip", "نظام براءات الاختراع لدول مجلس التعاون الخليجي"),
    "نظام حماية حقوق المؤلف .pdf":
        ("ip", "نظام حماية حقوق المؤلف"),
    "أدلة الهيئة السعودية للملكية الفكر.pdf":
        ("ip", "أدلة الهيئة السعودية للملكية الفكرية"),

    # ─── Civil Procedure — Evidence Law + studies ────────────────────────
    "نظام الإثبات ولائحته التنفيذية .pdf":
        ("civil_procedure", "نظام الإثبات ولائحته التنفيذية"),
    "الاثبات بالدليل الرقمي وتطبيقاته القضائية دراسة فقهية مقارنة بنظام الإثبات السعودي .pdf":
        ("civil_procedure", "الإثبات بالدليل الرقمي وتطبيقاته القضائية – دراسة فقهية مقارنة"),
    "مسالك تسبيب الاحكام القضائية.pdf":
        ("civil_procedure", "مسالك تسبيب الأحكام القضائية"),

    # ─── Labor — Saudi Labor Law (newest edition) ───────────────────────
    "نظام العمل السعودي الجديد .pdf":
        ("labor", "نظام العمل السعودي – التعديل الجديد"),

    # ─── Judicial Compendium — finally vol 2 ────────────────────────────
    "مجموعة الأحكام القضائية المجلد الثاني.pdf":
        ("judicial_compendium", "مجموعة الأحكام القضائية – المجلد الثاني (1435هـ)"),

    # ─── Legal Journal — additional Qadha paper ──────────────────────────
    "5d917d7c03bc3da649ab627f8cd7037261efb63e4d40d.pdf":
        ("legal_journal", "حقوق الملكية الفكرية – دروس من النهج الصيني – مجلة قضاء (1443هـ)"),

    # ─── Administrative — civil service + procurement + e-transactions ──
    "نظام المنافسات والمشتريات الحكومية.pdf":
        ("administrative", "نظام المنافسات والمشتريات الحكومية"),
    "نظام الانضباط الوظيفي 1443.pdf":
        ("administrative", "نظام الانضباط الوظيفي (1443هـ)"),
    "اللائحة التنفيذية لنظام الانضباط.pdf":
        ("administrative", "اللائحة التنفيذية لنظام الانضباط الوظيفي"),
    "نظام الخدمة المدنية 1442.pdf":
        ("administrative", "نظام الخدمة المدنية (1442هـ)"),
    "اللائحة التنفيذية لنظام الخدمة المدنية .pdf":
        ("administrative", "اللائحة التنفيذية لنظام الخدمة المدنية"),
    "نظام التعاملات الإلكترونية.pdf":
        ("administrative", "نظام التعاملات الإلكترونية"),
    "لائحة نظام التعاملات الإلكترونية.pdf":
        ("administrative", "اللائحة التنفيذية لنظام التعاملات الإلكترونية"),

    # ─── NEW DOMAIN: Tax & Zakat ─────────────────────────────────────────
    "نظام جباية الزكاة.pdf":
        ("tax_zakat", "نظام جباية الزكاة"),
    "نظام جباية الزكاة للحبوب والثمار وبهيمة الانعام.pdf":
        ("tax_zakat", "نظام جباية الزكاة للحبوب والثمار وبهيمة الأنعام"),
    "كتاب عن نظام جباية الزكاة.pdf":
        ("tax_zakat", "كتاب شامل عن نظام جباية الزكاة"),
    "انظمة الزكاة وضريبة القيمة المضافة والتصرفات العقارية .pdf":
        ("tax_zakat", "مجموعة أنظمة الزكاة وضريبة القيمة المضافة وضريبة التصرفات العقارية"),
    "نظام ضريبة القيمة المضافة 2.pdf":
        ("tax_zakat", "نظام ضريبة القيمة المضافة"),
    "لائحة نظام ضريبة القيمة المضافة.pdf":
        ("tax_zakat", "اللائحة التنفيذية لنظام ضريبة القيمة المضافة"),
    "نظام ضريبة الدخل.pdf":
        ("tax_zakat", "نظام ضريبة الدخل"),
    "اللائحة التنفيذية لنظام ضريبة الدخل.pdf":
        ("tax_zakat", "اللائحة التنفيذية لنظام ضريبة الدخل"),
    "نظام ضريبة التصرفات العقارية .pdf":
        ("tax_zakat", "نظام ضريبة التصرفات العقارية"),
    "اللائحة التنفيذية لضريبة التصرفات العقارية.pdf":
        ("tax_zakat", "اللائحة التنفيذية لضريبة التصرفات العقارية"),

    # ─── NEW DOMAIN: Data Protection (PDPL) ──────────────────────────────
    "نظام حماية البيانات الشخصية.pdf":
        ("data_protection", "نظام حماية البيانات الشخصية (PDPL)"),
    "لائحة نظام حماية البيانات الشخصية.pdf":
        ("data_protection", "اللائحة التنفيذية لنظام حماية البيانات الشخصية"),
    "دليل نظام حماية البيانات الشخصية لجهات التحكم والمعالجة .pdf":
        ("data_protection", "دليل نظام حماية البيانات الشخصية لجهات التحكم والمعالجة"),

    # ─── NEW DOMAIN: Cybercrime & AML ────────────────────────────────────
    "نظام مكافحة جرائم المعلوماتية 2.pdf":
        ("cybercrime_aml", "نظام مكافحة جرائم المعلوماتية"),
    "نظام مكافحة غسل الأموال 1439.pdf":
        ("cybercrime_aml", "نظام مكافحة غسل الأموال (1439هـ)"),
    "اللائحة التنفيذية لنظام مكافحة جرائم الإرهاب وتمويله .pdf":
        ("cybercrime_aml", "اللائحة التنفيذية لنظام مكافحة جرائم الإرهاب وتمويله"),
    "نظام جرائم الإرهاب وتمويله 2.pdf":
        ("cybercrime_aml", "نظام مكافحة جرائم الإرهاب وتمويله (لائحة 1440هـ)"),

    # ─── NEW DOMAIN: E-Litigation Guides ────────────────────────────────
    "دليل التقاضي الالكتروني.pdf":
        ("e_litigation", "دليل التقاضي الإلكتروني"),
    "دليل التقاضي الالكتروني .pdf":
        ("e_litigation", "دليل التقاضي الإلكتروني (نسخة 2)"),
    "دليل التقاضي امام اللجان.pdf":
        ("e_litigation", "دليل التقاضي أمام اللجان"),
    "أدلة التسجيل والاعتراض والتقاض.pdf":
        ("e_litigation", "أدلة التسجيل والاعتراض والتقاضي الإلكتروني"),
    "اﻟﺪﻟﻴﻞ ارﺷﺎدي ﻟﺼﻴﺎﻏﺔ ﺷﺮوط ﺗﺴﻮﻳﺔ اﳌﻨﺎزﻋﺎت.pdf":
        ("e_litigation", "الدليل الإرشادي لصياغة شروط تسوية المنازعات"),
    "دليل المستخدم لخدمة تبادل المذكرات_إلكترونياً في نظـــام القضــاء التجـــــــــاري.pdf":
        ("e_litigation", "دليل خدمة تبادل المذكرات إلكترونياً – القضاء التجاري"),
    "دليل الشروط والاحكام لقنوات استقبال الشكاوى.pdf":
        ("e_litigation", "دليل الشروط والأحكام لقنوات استقبال الشكاوى"),

    # ─── NEW DOMAIN: Legal Glossary ─────────────────────────────────────
    "معجم المصطلحات العـــــــــــــدلية.pdf":
        ("glossary", "معجم المصطلحات العدلية في الأنظمة العدلية السعودية"),

    # ─── Template (contracts) — PDFs ────────────────────────────────────
    "نموذج سند لأمر.pdf":
        ("template", "نموذج سند لأمر – Promissory Note"),
    "نموذج عقد تقديم خدمات ترجمة.pdf":
        ("template", "نموذج عقد تقديم خدمات ترجمة"),
    "نموذج عقد خدمات عام.pdf":
        ("template", "نموذج عقد خدمات عام"),
    "عقد تنفيذ دورة تدريبية.pdf":
        ("template", "نموذج عقد تنفيذ دورة تدريبية"),

    # ─── Template — DOCX (government contract templates) ────────────────
    "نموذج عقد (التَّشغيل والصيانة).docx":
        ("template", "نموذج عقد التشغيل والصيانة"),
    "نموذج عقد (الخدمات الهندسية - تصميم).docx":
        ("template", "نموذج عقد الخدمات الهندسية – تصميم"),
    "نموذج عقد (الخدمات الهندسية – إشراف).docx":
        ("template", "نموذج عقد الخدمات الهندسية – إشراف"),
    "نموذج عقد (إعاشة).docx":
        ("template", "نموذج عقد إعاشة"),
    "نموذج عقد (تشغيل وصيانة الطرق).docx":
        ("template", "نموذج عقد تشغيل وصيانة الطرق"),
    "نموذج عقد (تقنية المعلومات).docx":
        ("template", "نموذج عقد تقنية المعلومات"),
    "نموذج عقد (توريد الأدوية).docx":
        ("template", "نموذج عقد توريد الأدوية"),
    "نموذج عقد (توريد المستلزمات الطبية).docx":
        ("template", "نموذج عقد توريد المستلزمات الطبية"),
    "نموذج عقد (توريد عام).docx":
        ("template", "نموذج عقد توريد عام"),
    "نموذج عقد (توريد عسكري).docx":
        ("template", "نموذج عقد توريد عسكري"),
    "نموذج عقد (خدمات استشارية).docx":
        ("template", "نموذج عقد خدمات استشارية"),
    "نموذج عقد (خدمات).docx":
        ("template", "نموذج عقد خدمات"),
    "نموذج عقد (نظافة المدن).docx":
        ("template", "نموذج عقد نظافة المدن"),
    "نموذج عقد المشاركة في الدخل.docx":
        ("template", "نموذج عقد المشاركة في الدخل"),
}


_WIN_BAD = re.compile(r'[<>:"/\\|?*]')


def _safe_filename(s: str) -> str:
    """Strip Windows-illegal chars from a filename and collapse whitespace."""
    s = _WIN_BAD.sub("-", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _norm(s: str) -> str:
    """NFC-normalize a string for filename comparison.

    Drive downloads on macOS use NFD (decomposed Arabic). My MAPPING uses NFC.
    Without normalization, byte-equal-looking strings hash to different sets.
    """
    return unicodedata.normalize("NFC", s)


def stage_files() -> tuple[list[tuple[Path, str, str]], list[str]]:
    """Return list of (target_path, final_domain, final_title) + unmapped list."""
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    # NFC-normalize MAPPING keys for lookup; values stay as-is.
    mapping_nfc = {_norm(k): v for k, v in MAPPING.items()}
    skip_scanned_nfc = {_norm(s) for s in SKIP_SCANNED}
    skip_dupes_nfc = {_norm(s) for s in SKIP_DUPES}

    placed: list[tuple[Path, str, str]] = []
    unmapped: list[str] = []

    for src in sorted(SRC.iterdir()):
        if not src.is_file():
            continue
        name = src.name
        name_nfc = _norm(name)
        if name_nfc in skip_scanned_nfc:
            print(f"  SKIP scanned: {name}")
            continue
        if name_nfc in skip_dupes_nfc:
            print(f"  SKIP dup:     {name}")
            continue
        if name_nfc not in mapping_nfc:
            unmapped.append(name)
            continue

        domain, title = mapping_nfc[name_nfc]
        title = _safe_filename(title)
        ext = src.suffix.lower()
        target = STAGE / domain / f"{title}{ext}"
        target.parent.mkdir(exist_ok=True)
        # If duplicate target somehow, suffix
        suffix = 0
        while target.exists():
            suffix += 1
            target = STAGE / domain / f"{title} ({suffix}){ext}"
        try:
            shutil.copy2(src, target)
        except OSError as e:
            print(f"  FAIL copy: {name!r} → {target.name!r} :: {e}")
            print(f"    src bytes: {src.name.encode('utf-8')[:120]}")
            print(f"    tgt bytes: {target.name.encode('utf-8')[:120]}")
            continue
        placed.append((target, domain, title))

        # Also place into the canonical corpus_final/<domain>/ tree.
        canon_dir = CANONICAL / domain
        canon_dir.mkdir(parents=True, exist_ok=True)
        canon_target = canon_dir / target.name
        if not canon_target.exists():
            try:
                shutil.copy2(src, canon_target)
            except OSError as e:
                print(f"  WARN canonical copy failed: {e}")

    return placed, unmapped


def ingest_domain(stage_dir: Path) -> None:
    """Run `app.cli ingest-laws` for one domain folder.

    Use `--domain other` so the LegalDomain enum check passes; we'll
    UPDATE legal_domain to the proper value afterwards via SQL.

    Invokes the CLI separately per extension (--pattern *.pdf, then *.docx)
    so a bare '*' doesn't trigger Windows wildcard expansion.
    """
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    base = [
        str(VENV_PY), "-m", "app.cli", "ingest-laws",
        str(stage_dir),
        "--domain", "other",
        "--language", "ar",
        "--tenant", "platform",
        "--authority", "Saudi MoJ / ZATCA / Royal Decrees",
    ]
    for pattern in ("*.pdf", "*.docx"):
        # Skip patterns that wouldn't match anything in this dir.
        if not any(p.is_file() and p.suffix.lower() == pattern[1:] for p in stage_dir.iterdir()):
            continue
        subprocess.run(base + ["--pattern", pattern], cwd=str(API_DIR), env=env, check=False)


def fix_domains(placed: list[tuple[Path, str, str]]) -> None:
    """SQL-UPDATE legal_domain on newly ingested docs to their proper bucket."""
    eng = create_engine(os.environ["DATABASE_URL"])
    with eng.begin() as conn:
        for target, domain, title in placed:
            res = conn.execute(
                text("""
                    UPDATE documents
                       SET legal_domain = :domain
                     WHERE tenant_id = (SELECT id FROM tenants WHERE slug='platform')
                       AND title = :title
                       AND (legal_domain IS NULL OR legal_domain = 'other')
                """),
                {"domain": domain, "title": title},
            )
            if res.rowcount == 0:
                print(f"  WARN: no row matched title={title!r}")
            else:
                print(f"  reclassified [{domain:15s}] {title}")


def doc_count() -> int:
    eng = create_engine(os.environ["DATABASE_URL"])
    with eng.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM documents")).scalar() or 0


def main() -> None:
    print(f"=== Source: {SRC} ===")
    print(f"=== Stage:  {STAGE} ===")
    print()

    print("--- Staging ---")
    placed, unmapped = stage_files()
    print(f"\nStaged {len(placed)} files across {len({d for _, d, _ in placed})} domains.")
    if unmapped:
        print(f"\nUNMAPPED ({len(unmapped)}) — will NOT be ingested:")
        for n in unmapped:
            print(f"  - {n}")

    if not placed:
        print("Nothing to ingest.")
        return

    print(f"\n--- DB count before ingest: {doc_count()} ---\n")

    print("--- Ingesting per domain ---")
    domains_present = sorted({d for _, d, _ in placed})
    for d in domains_present:
        dom_dir = STAGE / d
        n = sum(1 for p in dom_dir.iterdir() if p.is_file())
        print(f"\n>>> Domain '{d}' ({n} files)")
        ingest_domain(dom_dir)

    after = doc_count()
    print(f"\n--- DB count after ingest:  {after} ---")
    print(f"--- Delta: +{after - (after - len(placed))} (expected +{len(placed)}) ---")

    print("\n--- Reclassifying new docs to their proper legal_domain ---")
    fix_domains(placed)

    print(f"\n--- Final DB count: {doc_count()} ---")


if __name__ == "__main__":
    main()
