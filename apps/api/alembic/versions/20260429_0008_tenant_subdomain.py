"""Tenant subdomain.

Adds `tenants.subdomain` so each subscribed firm can be reached at
`<subdomain>.<base_domain>`. Backfills from `slug` and adds a unique
constraint so two tenants can't claim the same subdomain.

Revision ID: 0008_tenant_subdomain
Revises: 0007_business_readiness
Create Date: 2026-04-29 14:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0008_tenant_subdomain"
down_revision: Union[str, None] = "0007_business_readiness"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("subdomain", sa.String(60), nullable=True),
    )
    # Backfill from slug for every existing tenant. `slug` is already
    # DNS-safe and unique, so this is safe.
    op.execute("UPDATE tenants SET subdomain = slug WHERE subdomain IS NULL")
    op.alter_column("tenants", "subdomain", nullable=False)
    op.create_index(
        "ix_tenants_subdomain", "tenants", ["subdomain"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_subdomain", table_name="tenants")
    op.drop_column("tenants", "subdomain")
