"""Lead intake: client status + per-contact WhatsApp conversations.

  - clients.status: lifecycle column (lead/prospect/active/archived). Defaults
    to 'active' so existing rows aren't reclassified.
  - conversations.whatsapp_contact_id: FK so each WhatsApp sender gets their
    own thread, even before they're linked to a CRM client.

Revision ID: 0003_lead_intake_fields
Revises: 0002_whatsapp_baileys
Create Date: 2026-04-28 00:30:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0003_lead_intake_fields"
down_revision: Union[str, None] = "0002_whatsapp_baileys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_index("ix_clients_status", "clients", ["status"])

    op.add_column(
        "conversations",
        sa.Column(
            "whatsapp_contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("whatsapp_contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_conversations_whatsapp_contact_id",
        "conversations",
        ["whatsapp_contact_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversations_whatsapp_contact_id",
        table_name="conversations",
    )
    op.drop_column("conversations", "whatsapp_contact_id")

    op.drop_index("ix_clients_status", table_name="clients")
    op.drop_column("clients", "status")
