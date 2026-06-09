"""Bulk-copy the platform corpus (documents + document_chunks, with embeddings)
from local Podman Postgres into Supabase via streaming COPY.

We rewrite the tenant_id column in the COPY source SELECT to Supabase's
platform-tenant UUID (the local + remote tenants differ, and the remote one
can't be re-keyed because seeded templates reference it).
"""
from __future__ import annotations

import psycopg

SRC = "postgresql://legalai:legalai@127.0.0.1:5433/legalai"
DST = "postgresql://postgres.szyyppmctwyqnwmaovyy:AbdAbd%40123.321@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"


def ordered_cols(cur, table: str) -> list[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


with psycopg.connect(SRC) as src, psycopg.connect(DST, connect_timeout=30) as dst:
    src.autocommit = True

    with src.cursor() as sc:
        sc.execute("SELECT id FROM tenants WHERE slug='platform'")
        local_tid = str(sc.fetchone()[0])
        doc_cols = ordered_cols(sc, "documents")
        chunk_cols = ordered_cols(sc, "document_chunks")
    with dst.cursor() as dc:
        dc.execute("SELECT id FROM tenants WHERE slug='platform'")
        dst_tid = str(dc.fetchone()[0])
    print(f"local tenant {local_tid} -> supabase tenant {dst_tid}")

    # Wipe any partial corpus on Supabase first.
    with dst.cursor() as dc:
        dc.execute("DELETE FROM document_chunks WHERE tenant_id=%s", (dst_tid,))
        dc.execute("DELETE FROM documents WHERE tenant_id=%s", (dst_tid,))
    dst.commit()

    # Disable the server-side statement timeout for this session so large
    # COPYs aren't cut off (Supabase defaults to a few seconds).
    with dst.cursor() as dc:
        dc.execute("SET statement_timeout = 0")
        dc.execute("SET idle_in_transaction_session_timeout = 0")
    dst.commit()

    def _sel(cols: list[str]) -> str:
        return ", ".join((f"'{dst_tid}'::uuid AS tenant_id" if c == "tenant_id" else c) for c in cols)

    # documents — small, single COPY.
    print("copying documents…")
    with src.cursor().copy(
        f"COPY (SELECT {_sel(doc_cols)} FROM documents WHERE tenant_id='{local_tid}'::uuid) TO STDOUT"
    ) as cout, dst.cursor().copy(f"COPY documents ({', '.join(doc_cols)}) FROM STDIN") as cin:
        for block in cout:
            cin.write(block)
    dst.commit()
    with dst.cursor() as dc:
        dc.execute("SELECT count(*) FROM documents WHERE tenant_id=%s", (dst_tid,))
        print("  documents in supabase:", dc.fetchone()[0])

    # document_chunks — batched per-document so each COPY is small + fast.
    print("copying document_chunks (with embeddings), per document…")
    with src.cursor() as sc:
        sc.execute("SELECT id FROM documents WHERE tenant_id=%s ORDER BY id", (local_tid,))
        doc_ids = [r[0] for r in sc.fetchall()]
    chunk_cols_in = ", ".join(chunk_cols)
    total = 0
    for i, did in enumerate(doc_ids, 1):
        copy_out = (
            f"COPY (SELECT {_sel(chunk_cols)} FROM document_chunks "
            f"WHERE document_id='{did}'::uuid) TO STDOUT"
        )
        with src.cursor().copy(copy_out) as cout, dst.cursor().copy(
            f"COPY document_chunks ({chunk_cols_in}) FROM STDIN"
        ) as cin:
            for block in cout:
                cin.write(block)
        dst.commit()
        if i % 20 == 0 or i == len(doc_ids):
            with dst.cursor() as dc:
                dc.execute("SELECT count(*) FROM document_chunks WHERE tenant_id=%s", (dst_tid,))
                total = dc.fetchone()[0]
            print(f"  {i}/{len(doc_ids)} docs → {total} chunks")
    print("  chunks in supabase:", total)

print("DONE — corpus bulk-transferred to Supabase.")
