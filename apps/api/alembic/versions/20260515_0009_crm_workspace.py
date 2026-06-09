"""CRM workspace: tasks, hearings, time entries, case notes, contacts, activities.

Also extends `cases` with court/litigation context and `clients` with KYC
+ lead-attribution columns so the existing CRUD endpoints carry the new
fields without breaking older API consumers.

Revision ID: 0009_crm_workspace
Revises: 0008_tenant_subdomain
Create Date: 2026-05-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0009_crm_workspace"
down_revision: Union[str, None] = "0008_tenant_subdomain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1. cases: court + lifecycle columns ----
    op.add_column("cases", sa.Column("priority", sa.String(16), nullable=False, server_default="medium"))
    op.add_column("cases", sa.Column("opposing_party_name", sa.String(300), nullable=True))
    op.add_column("cases", sa.Column("opposing_counsel", sa.String(300), nullable=True))
    op.add_column("cases", sa.Column("court_name", sa.String(200), nullable=True))
    op.add_column("cases", sa.Column("court_circuit", sa.String(120), nullable=True))
    op.add_column("cases", sa.Column("court_case_number", sa.String(80), nullable=True))
    op.add_column("cases", sa.Column("judge_name", sa.String(200), nullable=True))
    op.add_column("cases", sa.Column("opened_at", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("closed_at", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("next_hearing_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_cases_court_case_number", "cases", ["court_case_number"])
    op.create_index("ix_cases_next_hearing_at", "cases", ["next_hearing_at"])

    # ---- 2. clients: KYC + lead attribution ----
    op.add_column("clients", sa.Column("vat_number", sa.String(32), nullable=True))
    op.add_column("clients", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("clients", sa.Column("lead_source", sa.String(32), nullable=True))
    op.add_column("clients", sa.Column("referred_by", sa.String(200), nullable=True))
    op.add_column("clients", sa.Column("kyc_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("kyc_notes", sa.Text(), nullable=True))

    # ---- 3. tasks ----
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_tenant_status_due", "tasks", ["tenant_id", "status", "due_date"])
    op.create_index("ix_tasks_assignee", "tasks", ["assignee_id"])
    op.create_index("ix_tasks_case", "tasks", ["case_id"])

    # ---- 4. hearings ----
    op.create_table(
        "hearings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="hearing"),
        sa.Column("status", sa.String(32), nullable=False, server_default="scheduled"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("court_name", sa.String(200), nullable=True),
        sa.Column("court_circuit", sa.String(120), nullable=True),
        sa.Column("court_room", sa.String(64), nullable=True),
        sa.Column("judge_name", sa.String(200), nullable=True),
        sa.Column("opposing_counsel", sa.String(200), nullable=True),
        sa.Column("assigned_lawyer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hearings_tenant_scheduled", "hearings", ["tenant_id", "scheduled_at"])
    op.create_index("ix_hearings_case", "hearings", ["case_id"])
    op.create_index("ix_hearings_status", "hearings", ["status"])

    # ---- 5. time_entries ----
    op.create_table(
        "time_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_kind", sa.String(32), nullable=False, server_default="other"),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("billable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("billing_rate_per_hour", sa.Numeric(10, 2), nullable=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_time_entries_tenant_work_date", "time_entries", ["tenant_id", "work_date"])
    op.create_index("ix_time_entries_case", "time_entries", ["case_id"])
    op.create_index("ix_time_entries_user", "time_entries", ["user_id"])
    op.create_index("ix_time_entries_invoice", "time_entries", ["invoice_id"])

    # ---- 6. case_notes ----
    op.create_table(
        "case_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_notes_case", "case_notes", ["case_id"])

    # ---- 7. contacts ----
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="other"),
        sa.Column("organization", sa.String(200), nullable=True),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_tenant_kind", "contacts", ["tenant_id", "kind"])
    op.create_index("ix_contacts_name", "contacts", ["name"])

    # ---- 8. activities ----
    op.create_table(
        "activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False, server_default="other"),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activities_tenant_occurred", "activities", ["tenant_id", "occurred_at"])
    op.create_index("ix_activities_case", "activities", ["case_id"])
    op.create_index("ix_activities_client", "activities", ["client_id"])
    op.create_index("ix_activities_kind", "activities", ["kind"])


def downgrade() -> None:
    for table in ("activities", "contacts", "case_notes", "time_entries", "hearings", "tasks"):
        op.drop_table(table)

    for col in ("kyc_notes", "kyc_completed_at", "referred_by", "lead_source", "city", "vat_number"):
        op.drop_column("clients", col)

    op.drop_index("ix_cases_next_hearing_at", table_name="cases")
    op.drop_index("ix_cases_court_case_number", table_name="cases")
    for col in (
        "next_hearing_at", "closed_at", "opened_at",
        "judge_name", "court_case_number", "court_circuit", "court_name",
        "opposing_counsel", "opposing_party_name", "priority",
    ):
        op.drop_column("cases", col)
