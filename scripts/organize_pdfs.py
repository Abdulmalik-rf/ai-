"""Categorize the text-extractable PDFs into per-domain folders so
`ingest-laws --domain X ./folder` can be run once per domain.

Categorization is content-based (Arabic keywords in extracted text +
filename hints), then files are renamed to descriptive Arabic titles so
the platform corpus has readable Document.title rows.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "drive_raw"
CORPUS = ROOT / "data" / "corpus"

# Mapping decided from a manual review of the extracted first pages.
# `target_name` becomes the on-disk filename; `ingest-laws` uses the
# filename (without extension) as Document.title via --title-strategy filename.
PLAN: list[dict] = [
    # === Procedural / Civil (المرافعات) ===
    {
        "src": "01 - الحكم على المدعى عليه لتغيبه دون بينة.pdf",
        "domain": "other",
        "target_name": "بحث - الحكم على المدعى عليه لتغيبه دون بينة (الجمعية القضائية السعودية).pdf",
        "authority": "الجمعية العلمية القضائية السعودية (قضاء)",
    },
    {
        "src": "02 - المرافعة عن بعد.pdf",
        "domain": "other",
        "target_name": "بحث - المرافعة عن بعد (الجمعية القضائية السعودية).pdf",
        "authority": "الجمعية العلمية القضائية السعودية (قضاء)",
    },
    {
        "src": "03 - السوابق القضائية.pdf",
        "domain": "other",
        "target_name": "بحث - السوابق القضائية (الجمعية القضائية السعودية).pdf",
        "authority": "الجمعية العلمية القضائية السعودية (قضاء)",
    },
    # === Criminal (جزائي) ===
    {
        "src": "04 - السلطة التقديرية للقاضي الجزائي.pdf",
        "domain": "criminal",
        "target_name": "بحث - السلطة التقديرية للقاضي الجزائي (الجمعية القضائية السعودية).pdf",
        "authority": "الجمعية العلمية القضائية السعودية (قضاء)",
    },
    # === Intellectual Property (ملكية فكرية) ===
    {
        "src": "05 - إجراءات نظر دعاوى الملكية الفكرية.pdf",
        "domain": "ip",
        "target_name": "بحث - إجراءات نظر دعاوى الملكية الفكرية (المحكمة التجارية بالرياض).pdf",
        "authority": "المحكمة التجارية بالرياض",
    },
    # === MoJ Civil Procedure judgments collection — huge ===
    {
        "src": "1.pdf",
        "domain": "other",
        "target_name": "مجموعة الأحكام القضائية - قانون المرافعات 1435هـ (مركز البحوث - وزارة العدل).pdf",
        "authority": "مركز البحوث - وزارة العدل",
    },
    # === MoJ collected judgments (3rd edition, 2008/1429h) ===
    {
        "src": "50.pdf",
        "domain": "other",
        "target_name": "مدونة الأحكام القضائية - الإصدار الثالث 1429هـ (وزارة العدل).pdf",
        "authority": "الإدارة العامة لتدوين ونشر الأحكام - وزارة العدل",
    },
    # === MoJ monthly bulletins on regulatory updates ===
    {
        "src": "0jSlLnxiPkSM5f70l.pdf",
        "domain": "other",
        "target_name": "التقرير الشهري لمستجدات الأنظمة - الإصدار الخامس صفر 1441هـ (وزارة العدل).pdf",
        "authority": "مركز البحوث - وزارة العدل",
    },
    {
        "src": "E3whWapFW1smFNaut.pdf",
        "domain": "other",
        "target_name": "التقرير الشهري لمستجدات الأنظمة - الإصدار السادس ربيع الأول 1441هـ (وزارة العدل).pdf",
        "authority": "مركز البحوث - وزارة العدل",
    },
    {
        "src": "eP9pp7qApZEi4L3xV.pdf",
        "domain": "other",
        "target_name": "التقرير الشهري لمستجدات الأنظمة - الإصدار الأول شعبان-شوال 1440هـ (وزارة العدل).pdf",
        "authority": "مركز البحوث - وزارة العدل",
    },
    # === The mostly-empty one — keep but route to other ===
    {
        "src": "5ld2cEfJ2ESFQiZM1.pdf",
        "domain": "other",
        "target_name": "وثيقة قضائية بدون عنوان (5ld2c).pdf",
        "authority": "غير محدد",
    },
]


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _lookup(raw_dir: Path, name: str) -> Path | None:
    """Filenames on disk are in NFD; PLAN strings are in NFC. Match either."""
    target = _norm(name)
    for p in raw_dir.iterdir():
        if _norm(p.name) == target:
            return p
    return None


def main() -> None:
    if CORPUS.exists():
        shutil.rmtree(CORPUS)
    CORPUS.mkdir(parents=True)

    by_domain: dict[str, list[Path]] = {}
    missing: list[str] = []

    for entry in PLAN:
        src = _lookup(RAW, entry["src"])
        if src is None:
            missing.append(entry["src"])
            continue
        dom_dir = CORPUS / entry["domain"]
        dom_dir.mkdir(exist_ok=True)
        # NFC-normalize the target filename so the on-disk file name is canonical.
        dst = dom_dir / _norm(entry["target_name"])
        shutil.copy2(src, dst)
        by_domain.setdefault(entry["domain"], []).append(dst)

    print("Domain layout:")
    for dom, files in sorted(by_domain.items()):
        print(f"  {dom}: {len(files)} files")
        for f in files:
            print(f"    - {f.relative_to(CORPUS)}")
    if missing:
        print("\nMISSING source files:")
        for m in missing:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
