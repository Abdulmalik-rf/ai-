"""Multi-advisor memo review + final-submission review (Najiz gate).

Adds two related feature surfaces:

  1. `memo_reviews` + `memo_review_advisors`
        The Multi-Angle Legal Review System. A review fans out to N virtual
        advisors (10 max — Phase 1 ships 4: characterization, evidence,
        procedures, drafting), each producing an independent structured
        report. The final manager merges into a single executive summary
        + revised memo. We persist each advisor's full report so partial
        progress is visible while the rest run, and so users can re-read
        an old review without re-paying for LLM calls.

  2. `final_reviews`
        The "Final Review Before Submission to Najiz" gate. Not an advisor —
        a strict verification harness that runs 8 fixed checks (basis,
        statutes, facts/names/dates, requests, procedures, contradictions,
        hallucination, submission-readiness) and emits a binary verdict:
        READY / READY_WITH_OBSERVATIONS / NOT_READY. The verdict drives
        the UI's submit button — a "not_ready" verdict blocks accidental
        Najiz submission of a memo containing unsupported claims.

Revision ID: 0011_memo_review
Revises: 0010_user_phone_and_task_notify
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0011_memo_review"
down_revision: Union[str, None] = "0010_user_phone_and_task_notify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # memo_reviews — one row per review run
    # ---------------------------------------------------------------
    op.create_table(
        "memo_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # User-supplied case file (Stage 1 in the spec).
        sa.Column("case_title", sa.String(500), nullable=False),
        sa.Column("case_type", sa.String(120), nullable=True),
        sa.Column("facts", sa.Text(), nullable=True),
        sa.Column("claims", sa.Text(), nullable=True),
        sa.Column("memo_text", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        # Operating mode — standard (7 core advisors) / deep (all 10) /
        # custom (only the IDs listed in selected_advisors).
        sa.Column("mode", sa.String(16), nullable=False, server_default="deep"),
        sa.Column(
            "selected_advisors",
            postgresql.ARRAY(sa.String(64)),
            nullable=True,
        ),
        sa.Column("want_revised_memo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        # Lifecycle.
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Final manager output (Stage 5 in the spec) — merged report.
        # Schema documented in services/memo_review.py.
        sa.Column("final_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("revised_memo", sa.Text(), nullable=True),
        # Attached supporting documents — references to existing Documents
        # (preferred) or storage_keys (for ad-hoc uploads). Optional.
        sa.Column("attached_document_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memo_reviews_tenant_created", "memo_reviews", ["tenant_id", "created_at"])

    # ---------------------------------------------------------------
    # memo_review_advisors — one row per advisor within a review
    # ---------------------------------------------------------------
    op.create_table(
        "memo_review_advisors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memo_reviews.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # advisor_id: characterization / evidence / procedures / statutes /
        # facts / drafting / opponent / compensation / requests / risks.
        sa.Column("advisor_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Structured output — fixed shape (per spec §7):
        #   assessment ("strong"/"medium"/"weak")
        #   observations (3-5 strings)
        #   risk_points (1-3 strings)
        #   recommendations (2-4 strings)
        #   impact_level ("high"/"medium"/"low")
        #   extra (jsonb) — advisor-specific fields (e.g. compensation amount)
        sa.Column("assessment", sa.String(16), nullable=True),
        sa.Column("impact_level", sa.String(16), nullable=True),
        sa.Column("observations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("risk_points", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommendations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Raw LLM JSON response for debugging / re-merging.
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", "advisor_id", name="uq_memo_review_advisor"),
    )
    op.create_index("ix_memo_review_advisors_review_status", "memo_review_advisors", ["review_id", "status"])

    # ---------------------------------------------------------------
    # final_reviews — the Najiz pre-submission verification gate
    # ---------------------------------------------------------------
    op.create_table(
        "final_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        # Optional link to the multi-advisor review that produced this memo.
        sa.Column(
            "memo_review_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("memo_reviews.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("memo_text", sa.Text(), nullable=False),
        # Context (parties, facts, claims) — used to anchor verification.
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attached_document_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        # Lifecycle.
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Verdict — drives the UI submit button (spec §"Submission-readiness").
        #   ready | ready_with_observations | not_ready
        sa.Column("verdict", sa.String(32), nullable=True),
        # Aggregated risk_level — low / medium / high (spec).
        sa.Column("risk_level", sa.String(16), nullable=True),
        # 8 checks (basis, statutes, facts_names_dates, requests, procedures,
        # contradictions, hallucination, submission_readiness) — each is a
        # {status, findings[]} object keyed by check_id.
        sa.Column("checks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Top-level surfaces (mirrored from `checks` for fast filtering).
        sa.Column("critical_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("required_modifications", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("human_review_points", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_final_reviews_tenant_created", "final_reviews", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_final_reviews_tenant_created", table_name="final_reviews")
    op.drop_table("final_reviews")
    op.drop_index("ix_memo_review_advisors_review_status", table_name="memo_review_advisors")
    op.drop_table("memo_review_advisors")
    op.drop_index("ix_memo_reviews_tenant_created", table_name="memo_reviews")
    op.drop_table("memo_reviews")
