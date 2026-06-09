"""Export every document's identity + content sample from the DB to JSON.

For each of the ~96 docs in the platform tenant, pull:
  - id, title (auto-extracted), page_count, current legal_domain
  - storage_key (so we can map back to original file)
  - first ~2500 chars of concatenated chunk text (ordered by chunk_index)

The output JSON is what the reclassifier reads to assign a proper legal_domain
and a human-readable label for each document.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make app imports work
ROOT = Path(__file__).resolve().parent.parent / "apps" / "api"
sys.path.insert(0, str(ROOT))

# Force the same DB the API uses (port 5433)
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://legalai:legalai@127.0.0.1:5433/legalai",
)

from sqlalchemy import create_engine, text  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "doc_samples.json"


def main() -> None:
    url = os.environ["DATABASE_URL"]
    eng = create_engine(url)

    with eng.connect() as conn:
        # All docs
        docs = conn.execute(
            text(
                """
                SELECT id::text, title, page_count, legal_domain, storage_key
                FROM documents
                ORDER BY page_count DESC
                """
            )
        ).all()

        out = []
        for d in docs:
            doc_id, title, pages, domain, storage_key = d
            # Pull first 6 chunks of text (≈3000 chars usually) ordered by index
            rows = conn.execute(
                text(
                    """
                    SELECT content
                    FROM document_chunks
                    WHERE document_id = :id
                    ORDER BY chunk_index ASC
                    LIMIT 6
                    """
                ),
                {"id": doc_id},
            ).all()
            sample = " ".join((r[0] or "") for r in rows)
            sample = sample.strip()[:2500]
            # Original filename (last path segment of storage_key)
            orig_name = storage_key.rsplit("/", 1)[-1] if storage_key else ""
            out.append(
                {
                    "id": doc_id,
                    "title": title or "",
                    "filename": orig_name,
                    "pages": pages,
                    "domain": domain,
                    "sample": sample,
                }
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(out)} docs -> {OUT}")


if __name__ == "__main__":
    main()
