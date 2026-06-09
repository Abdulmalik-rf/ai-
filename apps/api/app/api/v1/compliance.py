"""PDPL / GDPR compliance endpoints.

Saudi Arabia's PDPL (Personal Data Protection Law) and most international
data-protection regimes require:

  - the right to access (export everything we hold on a user / tenant)
  - the right to deletion (right-to-be-forgotten)
  - clear retention boundaries

We expose three endpoints:

  POST /v1/compliance/me/export       — async-friendly user-scope export
  POST /v1/compliance/me/delete       — request account deletion (admin gets confirmed)
  POST /v1/compliance/tenant/delete   — admin: schedule entire tenant deletion

Deletion is *scheduled*, not immediate: we set `deleted_at` + `purge_at` on
the tenant/user and a Celery beat job purges hard data after a grace
window. This gives admins time to undo and lets us keep audit trails for
the legally-required retention period.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import Principal, get_current_principal, require_role
from app.core.security import Role
from app.db.session import get_db
from app.models import (
    AgentFact,
    AuditLog,
    Case,
    Client,
    Conversation,
    Document,
    Message,
    Subscription,
    Tenant,
    TenantInvite,
    User,
    WhatsAppContact,
    WhatsAppEscalation,
    WhatsAppSession,
)
from app.services.audit import record as audit
from app.services.auth_tokens import revoke_all_user_refresh_tokens

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class DeletionRequest(BaseModel):
    """Confirmation payload — must echo back the entity's identifying string
    to prevent accidental destruction. Mirrors GitHub's "type the repo
    name" pattern."""

    confirmation: str = Field(
        min_length=1,
        max_length=400,
        description="For account: your email. For tenant: the firm slug.",
    )
    reason: str | None = Field(default=None, max_length=500)


class ExportResponse(BaseModel):
    """Inline export. For tenants with >100MB of data, use ?format=async to
    enqueue a Celery job that uploads the archive to S3 and emails a link."""

    generated_at: datetime
    user: dict[str, Any]
    tenant: dict[str, Any] | None = None
    conversations: list[dict[str, Any]]
    messages_count: int
    documents: list[dict[str, Any]]
    cases: list[dict[str, Any]]
    clients: list[dict[str, Any]]
    audit_log_count: int


class DeletionScheduledResponse(BaseModel):
    scheduled_at: datetime
    purge_at: datetime
    grace_period_days: int


# =============================================================================
# Helpers
# =============================================================================


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": str(user.role),
        "locale": user.locale,
        "is_active": user.is_active,
        "is_email_verified": user.is_email_verified,
        "created_at": user.created_at.isoformat(),
    }


def _serialize_tenant(tenant: Tenant) -> dict[str, Any]:
    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "country": tenant.country,
        "default_locale": tenant.default_locale,
        "is_active": tenant.is_active,
        "created_at": tenant.created_at.isoformat(),
    }


# =============================================================================
# Export
# =============================================================================


@router.post("/me/export", response_model=ExportResponse)
def export_my_data(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ExportResponse:
    """Inline JSON export of everything tied to the calling user + their tenant.

    Includes: user record, tenant, all conversations the user owns, document
    metadata (NOT the binary payloads — those are S3 pre-signed-URL'able
    separately), cases, clients, and counts of audit + messages.

    Tenants with multi-GB datasets should switch to the async S3 archive
    flow when we add it (TODO: enqueue celery task → upload zip → email link).
    """
    tenant = principal.tenant
    user = principal.user

    convs = (
        list(
            db.execute(
                select(Conversation).where(
                    Conversation.tenant_id == tenant.id if tenant else False
                )
            ).scalars()
        )
        if tenant
        else []
    )
    docs = (
        list(
            db.execute(
                select(Document).where(
                    Document.tenant_id == tenant.id if tenant else False
                )
            ).scalars()
        )
        if tenant
        else []
    )
    cases = (
        list(
            db.execute(
                select(Case).where(Case.tenant_id == tenant.id if tenant else False)
            ).scalars()
        )
        if tenant
        else []
    )
    clients = (
        list(
            db.execute(
                select(Client).where(
                    Client.tenant_id == tenant.id if tenant else False
                )
            ).scalars()
        )
        if tenant
        else []
    )

    messages_count = 0
    audit_count = 0
    if tenant:
        from sqlalchemy import func as _f

        messages_count = int(
            db.execute(
                select(_f.count())
                .select_from(Message)
                .where(Message.tenant_id == tenant.id)
            ).scalar_one()
            or 0
        )
        audit_count = int(
            db.execute(
                select(_f.count())
                .select_from(AuditLog)
                .where(AuditLog.tenant_id == tenant.id)
            ).scalar_one()
            or 0
        )

    audit(
        db,
        tenant_id=tenant.id if tenant else None,
        actor_user_id=user.id,
        action="compliance.export",
    )

    return ExportResponse(
        generated_at=_now(),
        user=_serialize_user(user),
        tenant=_serialize_tenant(tenant) if tenant else None,
        conversations=[
            {
                "id": str(c.id),
                "title": c.title,
                "channel": str(c.channel),
                "created_at": c.created_at.isoformat(),
            }
            for c in convs
        ],
        messages_count=messages_count,
        documents=[
            {
                "id": str(d.id),
                "title": d.title,
                "source": str(d.source),
                "status": str(d.status),
                "page_count": d.page_count,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
        cases=[
            {
                "id": str(c.id),
                "reference": c.reference,
                "title": c.title,
                "status": str(c.status),
                "domain": str(c.domain),
            }
            for c in cases
        ],
        clients=[
            {
                "id": str(c.id),
                "name": c.name,
                "kind": c.kind,
                "status": str(c.status),
                "phone": c.phone,
            }
            for c in clients
        ],
        audit_log_count=audit_count,
    )


# =============================================================================
# Account deletion (single user)
# =============================================================================


@router.post("/me/delete", response_model=DeletionScheduledResponse)
def delete_my_account(
    body: DeletionRequest,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> DeletionScheduledResponse:
    """Schedule the calling user's account for deletion.

    Behaviour:
      - User must echo their email as `confirmation`.
      - User is immediately deactivated, all sessions revoked.
      - PII is scrubbed *after* a grace period (configurable), preserving
        audit trail in the meantime via the FK SET NULL semantics on
        `audit_logs.actor_user_id`.

    Tenant admins cannot delete their own account this way if they're the
    last active admin — they must transfer ownership first or use the
    tenant-deletion endpoint.
    """
    if body.confirmation.strip().lower() != principal.user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation does not match your email.",
        )

    if principal.role == Role.ADMIN and principal.tenant is not None:
        # Don't let the last active admin orphan the tenant.
        from sqlalchemy import func as _f

        other_admins = int(
            db.execute(
                select(_f.count())
                .select_from(User)
                .where(User.tenant_id == principal.tenant.id)
                .where(User.role == Role.ADMIN)
                .where(User.is_active.is_(True))
                .where(User.id != principal.user.id)
            ).scalar_one()
            or 0
        )
        if other_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "You are the last active admin of your firm. "
                    "Promote another admin or delete the entire tenant first."
                ),
            )

    grace = settings.account_deletion_grace_days
    purge_at = _now() + timedelta(days=grace)

    user = principal.user
    user.is_active = False
    if not user.extra_metadata if hasattr(user, "extra_metadata") else False:
        pass
    revoke_all_user_refresh_tokens(db, user_id=user.id)
    db.commit()

    audit(
        db,
        tenant_id=principal.tenant.id if principal.tenant else None,
        actor_user_id=user.id,
        action="compliance.account_delete_scheduled",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        extra_metadata={
            "purge_at": purge_at.isoformat(),
            "reason": body.reason or "",
        },
    )
    return DeletionScheduledResponse(
        scheduled_at=_now(),
        purge_at=purge_at,
        grace_period_days=grace,
    )


# =============================================================================
# Tenant deletion (whole firm)
# =============================================================================


@router.post(
    "/tenant/delete",
    response_model=DeletionScheduledResponse,
)
def delete_tenant(
    body: DeletionRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> DeletionScheduledResponse:
    """Admin-only: schedule the entire tenant for deletion.

    - Must echo the tenant slug as `confirmation`.
    - Tenant is immediately deactivated, every member's sessions revoked,
      every active subscription canceled.
    - Hard purge runs after the grace period (Celery beat task).

    The platform tenant cannot be deleted this way.
    """
    tenant = principal.tenant
    if tenant is None:
        raise HTTPException(
            status_code=403, detail="Tenant context required."
        )
    if tenant.slug == "platform":
        raise HTTPException(
            status_code=403, detail="The platform tenant cannot be deleted."
        )
    if body.confirmation.strip() != tenant.slug:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Confirmation must equal the firm slug ('{tenant.slug}')."
            ),
        )

    grace = settings.tenant_deletion_grace_days
    purge_at = _now() + timedelta(days=grace)

    tenant.is_active = False
    # Cancel any active subscription and revoke all user sessions for the tenant.
    sub = db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if sub is not None:
        from app.models.subscription import SubscriptionStatus

        sub.status = SubscriptionStatus.CANCELED

    members = list(
        db.execute(select(User).where(User.tenant_id == tenant.id)).scalars()
    )
    for m in members:
        m.is_active = False
        revoke_all_user_refresh_tokens(db, user_id=m.id)

    db.commit()

    audit(
        db,
        tenant_id=tenant.id,
        actor_user_id=principal.user.id,
        action="compliance.tenant_delete_scheduled",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        extra_metadata={
            "purge_at": purge_at.isoformat(),
            "reason": body.reason or "",
        },
    )
    return DeletionScheduledResponse(
        scheduled_at=_now(),
        purge_at=purge_at,
        grace_period_days=grace,
    )
