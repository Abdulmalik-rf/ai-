"""Staff phone numbers + task notification tracking.

Adds:
  - users.phone_number          — staff WhatsApp number; when set we auto-add
                                  it to the tenant's WhatsApp allowlist.
  - tasks.notified_at           — when we last sent the WhatsApp "you've got
                                  a new task" message to the assignee.
  - tasks.due_reminder_sent_at  — when we sent the "task due today/overdue"
                                  reminder so the sweep doesn't spam.

Revision ID: 0010_user_phone_and_task_notify
Revises: 0009_crm_workspace
Create Date: 2026-05-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010_user_phone_and_task_notify"
down_revision: Union[str, None] = "0009_crm_workspace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("phone_number", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_users_phone_number",
        "users",
        ["phone_number"],
        unique=False,
    )

    op.add_column(
        "tasks",
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "due_reminder_sent_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "due_reminder_sent_at")
    op.drop_column("tasks", "notified_at")
    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_column("users", "phone_number")
