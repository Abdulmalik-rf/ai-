"""Business-readiness columns + invoices.

  - tenants: vat_number, billing_email, billing_address (B2B invoicing)
  - tenants: onboarding_state, onboarding_completed_at (wizard tracking)
  - tenants + users: deletion_scheduled_at, purge_at (PDPL right-to-be-forgotten)
  - new table `invoices`: VAT-compliant subscription invoices

Revision ID: 0007_business_readiness
Revises: 0006_auth_hardening
Create Date: 2026-04-29 12:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0007_business_readiness"
down_revision: Union[str, None] = "0006_auth_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- tenants -----------------------------------------------------------
    op.add_column("tenants", sa.Column("vat_number", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("billing_email", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("billing_address", sa.Text, nullable=True))
    op.add_column(
        "tenants",
        sa.Column(
            "onboarding_state",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("deletion_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants", sa.Column("purge_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_tenants_purge_at", "tenants", ["purge_at"])

    # ---- users -------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column("deletion_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users", sa.Column("purge_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_users_purge_at", "users", ["purge_at"])

    # ---- invoices ----------------------------------------------------------
    op.create_table(
        "invoices",
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
        sa.Column("number", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="SAR"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("vat_rate", sa.Numeric(5, 4), nullable=False, server_default="0.15"),
        sa.Column("vat_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("seller_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("seller_vat_number", sa.String(20), nullable=True),
        sa.Column("seller_address", sa.Text, nullable=True),
        sa.Column("buyer_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("buyer_vat_number", sa.String(20), nullable=True),
        sa.Column("buyer_address", sa.Text, nullable=True),
        sa.Column("buyer_email", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(16), nullable=True),
        sa.Column("provider_invoice_id", sa.String(80), nullable=True),
        sa.Column(
            "line_items",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("zatca_qr", sa.Text, nullable=True),
        sa.Column("pdf_storage_key", sa.String(500), nullable=True),
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
            "tenant_id", "number", name="uq_invoices_tenant_number"
        ),
    )
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])
    op.create_index("ix_invoices_number", "invoices", ["number"])
    op.create_index(
        "ix_invoices_subscription_id", "invoices", ["subscription_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_subscription_id", table_name="invoices")
    op.drop_index("ix_invoices_number", table_name="invoices")
    op.drop_index("ix_invoices_tenant_id", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_users_purge_at", table_name="users")
    op.drop_column("users", "purge_at")
    op.drop_column("users", "deletion_scheduled_at")

    op.drop_index("ix_tenants_purge_at", table_name="tenants")
    op.drop_column("tenants", "purge_at")
    op.drop_column("tenants", "deletion_scheduled_at")
    op.drop_column("tenants", "onboarding_completed_at")
    op.drop_column("tenants", "onboarding_state")
    op.drop_column("tenants", "billing_address")
    op.drop_column("tenants", "billing_email")
    op.drop_column("tenants", "vat_number")
