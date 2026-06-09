"""Legal corpus metadata.

Adds the columns the RAG layer needs to:
  - filter retrieval by legal domain (commercial, labor, family…),
  - return article-aware citations ("Article 75 of the Labor Law"),
  - surface authority + decree references in the UI.

All new columns are nullable so existing documents/chunks keep working
without a backfill — the retriever treats NULL domain as "any".

Revision ID: 0005_legal_corpus_metadata
Revises: 0004_agent_profile
Create Date: 2026-04-28 02:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_legal_corpus_metadata"
down_revision: Union[str, None] = "0004_agent_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- documents -----------------------------------------------------------
    op.add_column(
        "documents",
        sa.Column("legal_domain", sa.String(32), nullable=True),
    )
    op.create_index("ix_documents_legal_domain", "documents", ["legal_domain"])

    op.add_column("documents", sa.Column("authority", sa.String(200), nullable=True))
    op.add_column(
        "documents", sa.Column("decree_number", sa.String(64), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("enacted_at", sa.Date(), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("effective_at", sa.Date(), nullable=True)
    )
    op.add_column("documents", sa.Column("version", sa.String(64), nullable=True))
    op.add_column(
        "documents", sa.Column("source_url", sa.String(500), nullable=True)
    )

    # --- document_chunks -----------------------------------------------------
    op.add_column(
        "document_chunks",
        sa.Column("legal_domain", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_document_chunks_legal_domain",
        "document_chunks",
        ["legal_domain"],
    )
    op.add_column(
        "document_chunks",
        sa.Column("article_number", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_document_chunks_article_number",
        "document_chunks",
        ["article_number"],
    )
    op.add_column(
        "document_chunks",
        sa.Column("heading", sa.String(500), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "section_path",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "section_path")
    op.drop_column("document_chunks", "heading")
    op.drop_index(
        "ix_document_chunks_article_number", table_name="document_chunks"
    )
    op.drop_column("document_chunks", "article_number")
    op.drop_index(
        "ix_document_chunks_legal_domain", table_name="document_chunks"
    )
    op.drop_column("document_chunks", "legal_domain")

    op.drop_column("documents", "source_url")
    op.drop_column("documents", "version")
    op.drop_column("documents", "effective_at")
    op.drop_column("documents", "enacted_at")
    op.drop_column("documents", "decree_number")
    op.drop_column("documents", "authority")
    op.drop_index("ix_documents_legal_domain", table_name="documents")
    op.drop_column("documents", "legal_domain")
