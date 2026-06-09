"""WhatsApp sessions, allowed senders, and agent facts.

Adds the tables that back the QR-pairing flow and the long-term agent memory:

  - whatsapp_sessions: per-tenant Baileys session state (mirrors the bridge).
  - whatsapp_allowed_senders: per-tenant phone allowlist for the agent.
  - agent_facts: capped long-term facts injected into the agent system prompt.

Revision ID: 0002_whatsapp_baileys
Revises: 0001_initial_schema
Create Date: 2026-04-28 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0002_whatsapp_baileys"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_sessions",
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
        sa.Column("status", sa.String(32), nullable=False, server_default="disconnected"),
        sa.Column("phone_number", sa.String(32), nullable=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("last_qr", sa.Text, nullable=True),
        sa.Column("last_qr_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_disconnect_reason", sa.String(200), nullable=True),
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
        sa.UniqueConstraint("tenant_id", name="uq_whatsapp_sessions_tenant_id"),
    )
    op.create_index(
        "ix_whatsapp_sessions_tenant_id",
        "whatsapp_sessions",
        ["tenant_id"],
    )

    op.create_table(
        "whatsapp_allowed_senders",
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
        sa.Column("wa_phone", sa.String(32), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
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
        sa.UniqueConstraint(
            "tenant_id",
            "wa_phone",
            name="uq_whatsapp_allowed_senders_tenant_phone",
        ),
    )
    op.create_index(
        "ix_whatsapp_allowed_senders_tenant_id",
        "whatsapp_allowed_senders",
        ["tenant_id"],
    )
    op.create_index(
        "ix_whatsapp_allowed_senders_wa_phone",
        "whatsapp_allowed_senders",
        ["wa_phone"],
    )

    op.create_table(
        "agent_facts",
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
        sa.Column(
            "whatsapp_contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("text", sa.String(400), nullable=False),
        sa.Column(
            "extra_metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
    )
    op.create_index("ix_agent_facts_tenant_id", "agent_facts", ["tenant_id"])
    op.create_index(
        "ix_agent_facts_whatsapp_contact_id",
        "agent_facts",
        ["whatsapp_contact_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_facts_whatsapp_contact_id", table_name="agent_facts")
    op.drop_index("ix_agent_facts_tenant_id", table_name="agent_facts")
    op.drop_table("agent_facts")

    op.drop_index(
        "ix_whatsapp_allowed_senders_wa_phone",
        table_name="whatsapp_allowed_senders",
    )
    op.drop_index(
        "ix_whatsapp_allowed_senders_tenant_id",
        table_name="whatsapp_allowed_senders",
    )
    op.drop_table("whatsapp_allowed_senders")

    op.drop_index(
        "ix_whatsapp_sessions_tenant_id", table_name="whatsapp_sessions"
    )
    op.drop_table("whatsapp_sessions")
