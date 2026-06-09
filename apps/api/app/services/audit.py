"""Convenience helpers for writing to the audit log."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    *,
    tenant_id: UUID | None,
    actor_user_id: UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    extra_metadata: dict | None = None,
) -> None:
    if tenant_id is None:
        # Audit logs require a tenant. For platform-level events we use the
        # platform tenant (see seed). Skip if absolutely no context.
        return
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_metadata=extra_metadata or {},
        )
    )
    db.commit()
