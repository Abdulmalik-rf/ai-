"""Consultations — the Legal Opinion Engine (advisory panel + synthesizer + gate).

Revision ID: 0012_consultations
Revises: 0011_memo_review
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0012_consultations"
down_revision: Union[str, None] = "0011_memo_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consultations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("client_type", sa.String(40), nullable=True),
        sa.Column("domain", sa.String(40), nullable=True),
        sa.Column("mode", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("attached_document_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("framing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("grounding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("final_opinion", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("verification", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence_level", sa.String(16), nullable=True),
        sa.Column("needs_human_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consultations_tenant_created", "consultations", ["tenant_id", "created_at"])

    op.create_table(
        "consultation_advisors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("advisor_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("position", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(16), nullable=True),
        sa.Column("key_points", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("caveats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consultation_id", "advisor_id", name="uq_consultation_advisor"),
    )
    op.create_index("ix_consultation_advisors_consultation_status", "consultation_advisors", ["consultation_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_consultation_advisors_consultation_status", table_name="consultation_advisors")
    op.drop_table("consultation_advisors")
    op.drop_index("ix_consultations_tenant_created", table_name="consultations")
    op.drop_table("consultations")
