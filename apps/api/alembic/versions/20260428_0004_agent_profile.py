"""Per-tenant agent tuning profile.

Backs the dashboard's "Teach your agent" page. One row per tenant, every
field optional — fields the lawyer leaves blank fall back to the baseline
prompt.

Revision ID: 0004_agent_profile
Revises: 0003_lead_intake_fields
Create Date: 2026-04-28 01:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_agent_profile"
down_revision: Union[str, None] = "0003_lead_intake_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("firm_display_name", sa.String(200), nullable=True),
        sa.Column("welcome_message_ar", sa.Text, nullable=True),
        sa.Column("welcome_message_en", sa.Text, nullable=True),
        sa.Column("firm_specialties", sa.Text, nullable=True),
        sa.Column("consultation_offer", sa.Text, nullable=True),
        sa.Column("tone_guidelines", sa.Text, nullable=True),
        sa.Column("custom_instructions", sa.Text, nullable=True),
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default="Asia/Riyadh",
        ),
        sa.Column(
            "enabled_domains",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", name="uq_agent_profiles_tenant_id"),
    )
    op.create_index(
        "ix_agent_profiles_tenant_id",
        "agent_profiles",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_profiles_tenant_id", table_name="agent_profiles")
    op.drop_table("agent_profiles")
