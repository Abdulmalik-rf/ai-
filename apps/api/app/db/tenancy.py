"""Tenant-scoped query helpers.

Every business query goes through `TenantQuery.for_tenant(...)` so that we can't
accidentally leak rows across firms. This is enforced at three layers:

1. Schema: `TenantMixin` adds a non-null FK on every tenant-scoped table.
2. Query helpers (this file).
3. Service layer: services always receive a `tenant_id` and pass it down.
"""
from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.base import TenantMixin

T = TypeVar("T", bound=TenantMixin)


class TenantQuery:
    """Helpers that always filter by tenant_id."""

    @staticmethod
    def for_tenant(model: type[T], tenant_id: UUID) -> Select:
        return select(model).where(model.tenant_id == tenant_id)

    @staticmethod
    def get(db: Session, model: type[T], tenant_id: UUID, obj_id: UUID) -> T | None:
        stmt = TenantQuery.for_tenant(model, tenant_id).where(model.id == obj_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_(
        db: Session,
        model: type[T],
        tenant_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[T]:
        stmt = (
            TenantQuery.for_tenant(model, tenant_id)
            .order_by(model.created_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
            .offset(offset)
        )
        return list(db.execute(stmt).scalars().all())
