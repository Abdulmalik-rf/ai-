"""Re-ingest the already-staged corpus_final tree into a fresh DB.

Used after Postgres data was lost (e.g. switching from Docker Desktop volumes
to Podman volumes). The corpus_final/ tree on the host filesystem survives —
this script feeds each domain folder through `app.cli ingest-laws`.

Run:  python scripts/reingest_from_corpus_final.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "apps" / "api"
VENV_PY = API_DIR / ".venv" / "Scripts" / "python.exe"
CORPUS = ROOT / "data" / "corpus_final"

# Map our 20 display-buckets to the LegalDomain enum value we ingest under.
# Anything not in the enum gets ingested as "other" and we UPDATE legal_domain
# afterwards via SQL (matching unified_ingest's contract).
ENUM_DOMAINS = {"commercial", "labor", "family", "criminal", "real_estate",
                "administrative", "ip", "corporate", "banking", "other"}


def main() -> None:
    if not CORPUS.exists():
        sys.exit(f"corpus dir missing: {CORPUS}")

    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        # local sentence-transformers — no HF round-trip per file.
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }

    # Reclassification map: subdomain folder name → final legal_domain.
    # These are the values build_corpus_report.py renders against. Anything
    # not in the enum is staged as "other" then UPDATEd via direct SQL.
    domains = sorted(p for p in CORPUS.iterdir() if p.is_dir())
    print(f"Domains found: {len(domains)}")

    total_files = 0
    domain_targets: list[tuple[str, str, int]] = []  # (folder, cli_enum, file_count)
    for d in domains:
        files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".pdf", ".docx")]
        total_files += len(files)
        cli_enum = d.name if d.name in ENUM_DOMAINS else "other"
        domain_targets.append((d.name, cli_enum, len(files)))
        print(f"  {d.name:25s} -> ingest as {cli_enum:15s} ({len(files)} files)")

    print(f"\nTotal: {total_files} files\n")

    for folder, cli_enum, count in domain_targets:
        if count == 0:
            continue
        print(f"\n=== {folder} ({count} files) ===")
        # Two passes per dir: *.pdf then *.docx (Windows glob doesn't support
        # brace expansion).
        for pattern in ("*.pdf", "*.docx"):
            d = CORPUS / folder
            if not any(p.is_file() and p.suffix.lower() == pattern[1:] for p in d.iterdir()):
                continue
            cmd = [
                str(VENV_PY), "-m", "app.cli", "ingest-laws",
                str(d),
                "--domain", cli_enum,
                "--language", "ar",
                "--tenant", "platform",
                "--authority", "Saudi MoJ / ZATCA / Royal Decrees",
                "--pattern", pattern,
            ]
            subprocess.run(cmd, cwd=str(API_DIR), env=env, check=False)

    # SQL-UPDATE legal_domain for the non-enum domains so the report renders
    # them under their proper buckets (civil, civil_procedure, judicial_compendium, etc.).
    print("\n--- Reclassifying non-enum buckets ---")
    sys.path.insert(0, str(API_DIR))
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://legalai:legalai@127.0.0.1:5433/legalai",
    )
    from sqlalchemy import create_engine, text
    eng = create_engine(os.environ["DATABASE_URL"])

    # Folder name → desired final legal_domain value (varchar(32)).
    final_domain_for = {
        "civil_procedure":     "civil_procedure",
        "criminal_procedure":  "criminal_procedure",
        "tax_zakat":           "tax_zakat",
        "data_protection":     "data_protection",
        "cybercrime_aml":      "cybercrime_aml",
        "e_litigation":        "e_litigation",
        "glossary":            "glossary",
        "judicial_compendium": "judicial_compendium",
        "legal_journal":       "legal_journal",
        "research_paper":      "research_paper",
        "practice_guide":      "practice_guide",
        "legal_updates":       "legal_updates",
        "template":            "template",
        "civil":               "civil",
        # commercial/labor/family/ip/administrative/banking/real_estate
        # already match the enum so they stay as-is.
    }

    with eng.begin() as conn:
        for folder, final_d in final_domain_for.items():
            d = CORPUS / folder
            if not d.exists():
                continue
            files = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in (".pdf", ".docx")]
            for f in files:
                title = f.stem
                res = conn.execute(
                    text(
                        "UPDATE documents SET legal_domain=:dom "
                        "WHERE tenant_id=(SELECT id FROM tenants WHERE slug='platform') "
                        "AND title=:title AND legal_domain='other'"
                    ),
                    {"dom": final_d, "title": title},
                )
                if res.rowcount:
                    print(f"  [{final_d:20s}] {title[:60]}")

    # Final tally.
    with eng.connect() as conn:
        docs = conn.execute(text(
            "SELECT COUNT(*) FROM documents d JOIN tenants t ON t.id=d.tenant_id "
            "WHERE t.slug='platform'"
        )).scalar()
        chunks = conn.execute(text(
            "SELECT COUNT(*) FROM document_chunks dc "
            "JOIN documents d ON d.id=dc.document_id "
            "JOIN tenants t ON t.id=d.tenant_id WHERE t.slug='platform'"
        )).scalar()
        print(f"\n=== DONE: {docs} docs / {chunks} chunks in the platform tenant ===")


if __name__ == "__main__":
    main()
