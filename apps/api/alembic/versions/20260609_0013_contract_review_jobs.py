"""Contract-review jobs — async multi-advisor contract review with progress.

A job tracks the advisor panel's progress (in `advisors` JSONB) so the UI can
poll and show advisors finishing one-by-one instead of a 3-minute spinner.
The final synthesized review lands in `result` (and is also mirrored onto the
document's extra_metadata for backward compatibility with the old sync path).

Revision ID: 0013_contract_review_jobs
Revises: 0012_consultations
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0013_contract_review_jobs"
down_revision: Union[str, None] = "0012_consultations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contract_review_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("mode", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("locale", sa.String(8), nullable=False, server_default="ar"),
        # advisors: [{advisor_id, name, status, favors, findings_count}]
        sa.Column("advisors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contract_review_jobs_doc_created", "contract_review_jobs", ["document_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_contract_review_jobs_doc_created", table_name="contract_review_jobs")
    op.drop_table("contract_review_jobs")
