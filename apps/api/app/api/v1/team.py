"""Team management — tenant admins managing their own users + invites.

Distinct from `/v1/admin/*` which is platform-level super-admin only.

  GET    /v1/team/users                — list members
  PATCH  /v1/team/users/{id}           — change role / activate / deactivate
  DELETE /v1/team/users/{id}           — deactivate (soft-delete; preserves audit trail)

  GET    /v1/team/invites              — list pending/accepted invites
  POST   /v1/team/invites              — issue a new invite (sends email)
  DELETE /v1/team/invites/{id}         — revoke a pending invite

Seat caps from the active subscription are enforced on POST /invites and on
PATCH that re-activates a user. Hits the 402 path consistent with the rest
of the billing surface.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Principal, require_role
from app.core.security import Role, hash_password
from app.db.session import get_db
from app.models import Plan, Subscription, TenantInvite, User
from app.schemas.user import UserRead
from app.services.audit import record as audit
from app.services.auth_tokens import (
    AuthTokenError,
    consume_invite,
    issue_invite,
    normalize_email,
)
from app.services.email import render_invite_email, send_email
from app.services.staff_notify import normalize_phone, sync_user_allowlist

router = APIRouter()


# =============================================================================
# Schemas (kept inline — small surface area, only used here)
# =============================================================================


class TeamUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    locale: str | None = Field(default=None, pattern=r"^(ar|en)$")
    full_name: str | None = Field(default=None, max_length=200)
    # Empty string means "clear the phone"; null means "don't touch".
    phone_number: str | None = Field(default=None, max_length=32)


class StaffCreate(BaseModel):
    """Admin-only "add a staff member directly" payload.

    Skips the e-mail invite flow: useful for an office assistant or a
    paralegal who doesn't need a dashboard login on day one but should
    receive WhatsApp pings the moment a matter is assigned to them.
    """

    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    phone_number: str | None = Field(default=None, max_length=32)
    role: Role = Role.LAWYER
    locale: str = Field(default="ar", pattern=r"^(ar|en)$")
    is_active: bool = True


class InviteCreate(BaseModel):
    email: EmailStr
    role: Role = Role.LAWYER


class InviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: str
    invited_by_user_id: UUID | None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


# =============================================================================
# Helpers
# =============================================================================


def _seat_cap(db: Session, *, tenant_id: UUID) -> int | None:
    """Returns the seat cap for the tenant's active subscription, or None
    when there's no subscription / it's an unlimited plan."""
    sub = db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.tenant_id == tenant_id)
    ).first()
    if sub is None:
        return None
    _, plan = sub
    if plan.seats_limit and plan.seats_limit > 0:
        return plan.seats_limit
    return None


def _seats_used(db: Session, *, tenant_id: UUID) -> int:
    """Active members + outstanding (unrevoked, unaccepted) invites."""
    active_users = db.execute(
        select(func.count())
        .select_from(User)
        .where(User.tenant_id == tenant_id)
        .where(User.is_active.is_(True))
    ).scalar_one()
    pending_invites = db.execute(
        select(func.count())
        .select_from(TenantInvite)
        .where(TenantInvite.tenant_id == tenant_id)
        .where(TenantInvite.accepted_at.is_(None))
        .where(TenantInvite.revoked_at.is_(None))
        .where(TenantInvite.expires_at > datetime.now(timezone.utc))
    ).scalar_one()
    return int(active_users or 0) + int(pending_invites or 0)


def _check_seat_capacity(db: Session, *, tenant_id: UUID, adding: int = 1) -> None:
    cap = _seat_cap(db, tenant_id=tenant_id)
    if cap is None:
        return
    used = _seats_used(db, tenant_id=tenant_id)
    if used + adding > cap:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Seat limit reached ({used}/{cap}). Upgrade your plan or "
                f"deactivate an existing member first."
            ),
        )


# =============================================================================
# Members
# =============================================================================


@router.get("/users", response_model=list[UserRead])
def list_users(
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN, Role.LAWYER))],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserRead]:
    rows = list(
        db.execute(
            select(User)
            .where(User.tenant_id == principal.tenant_id)
            .order_by(User.created_at.asc())
        ).scalars()
    )
    return [UserRead.model_validate(u) for u in rows]


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    body: TeamUserUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    target = db.execute(
        select(User).where(
            User.id == user_id, User.tenant_id == principal.tenant_id
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == principal.user.id and body.role is not None and body.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote yourself. Promote another admin first.",
        )

    payload = body.model_dump(exclude_unset=True)
    # If we're (re)activating the user, ensure we still have a seat.
    if payload.get("is_active") is True and not target.is_active:
        _check_seat_capacity(db, tenant_id=principal.tenant_id, adding=1)

    # Track the previous phone for allowlist reconciliation, then normalise
    # the new value before assigning so we always store digits-only.
    previous_phone = target.phone_number
    if "phone_number" in payload:
        payload["phone_number"] = normalize_phone(payload["phone_number"])

    for field, value in payload.items():
        setattr(target, field, value)

    # Reconcile the WhatsApp allowlist (and update label on name change).
    if "phone_number" in payload or "full_name" in payload:
        sync_user_allowlist(db, user=target, previous_phone=previous_phone)

    db.commit()
    db.refresh(target)
    audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user.id,
        action="team.user_updated",
        target_type="user",
        target_id=str(target.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        extra_metadata={"changes": payload},
    )
    return UserRead.model_validate(target)


@router.post(
    "/staff",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_staff(
    body: StaffCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """Add a staff member directly (admin convenience).

    Differences from POST /team/invites:
      - no e-mail round-trip: the row is created active immediately,
      - phone_number is first-class, and when set is mirrored to the
        WhatsApp allowlist for the tenant,
      - the password is randomised; the admin can issue a reset link from
        /team/users later if they want this person to log in to the
        dashboard. Useful for office staff who only ever need WhatsApp
        notifications, never the web UI.
    """
    if body.role == Role.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="super_admin can only be assigned by platform staff.",
        )

    email = normalize_email(body.email)
    existing = db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This email is already registered. "
                "Use /team/users to update the existing record."
            ),
        )

    if body.is_active:
        _check_seat_capacity(db, tenant_id=principal.tenant_id, adding=1)

    # Randomised throwaway password — the staffer can reset it later via the
    # standard forgot-password flow. We never surface it.
    import secrets

    user = User(
        tenant_id=principal.tenant_id,
        email=email,
        full_name=body.full_name,
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        role=body.role,
        locale=body.locale,
        is_active=body.is_active,
        is_email_verified=False,
        phone_number=normalize_phone(body.phone_number),
    )
    db.add(user)
    db.flush()
    sync_user_allowlist(db, user=user, previous_phone=None)
    db.commit()
    db.refresh(user)

    audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user.id,
        action="team.staff_created",
        target_type="user",
        target_id=str(user.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        extra_metadata={"email": email, "role": body.role.value},
    )
    return UserRead.model_validate(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def deactivate_user(
    user_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Soft-delete: deactivates the user. We never hard-delete because the
    audit trail (cases, conversations, …) references them."""
    target = db.execute(
        select(User).where(
            User.id == user_id, User.tenant_id == principal.tenant_id
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.id == principal.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate yourself.",
        )
    target.is_active = False
    # Drop their WhatsApp allowlist row so a deactivated staffer loses
    # agent access too. We pass the previous_phone and *clear* phone_number
    # so sync_user_allowlist treats it as "phone removed".
    previous_phone = target.phone_number
    target.phone_number = None
    sync_user_allowlist(db, user=target, previous_phone=previous_phone)
    db.commit()
    audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user.id,
        action="team.user_deactivated",
        target_type="user",
        target_id=str(target.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


# =============================================================================
# Invites
# =============================================================================


@router.get("/invites", response_model=list[InviteRead])
def list_invites(
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> list[InviteRead]:
    rows = list(
        db.execute(
            select(TenantInvite)
            .where(TenantInvite.tenant_id == principal.tenant_id)
            .order_by(TenantInvite.created_at.desc())
        ).scalars()
    )
    return [InviteRead.model_validate(r) for r in rows]


@router.post(
    "/invites",
    response_model=InviteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    body: InviteCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> InviteRead:
    if body.role == Role.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="super_admin can only be assigned by platform staff.",
        )

    email = normalize_email(body.email)
    # Already a member of this tenant? Don't bother emailing.
    existing = db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        if existing.tenant_id == principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This person is already a member of your firm.",
            )
        # Member of a different tenant — they need a different email.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered to another firm.",
        )

    # Reject if there's already a live invite for this email.
    pending = db.execute(
        select(TenantInvite).where(
            TenantInvite.tenant_id == principal.tenant_id,
            TenantInvite.email == email,
            TenantInvite.accepted_at.is_(None),
            TenantInvite.revoked_at.is_(None),
            TenantInvite.expires_at > datetime.now(timezone.utc),
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active invite already exists for this email.",
        )

    _check_seat_capacity(db, tenant_id=principal.tenant_id, adding=1)

    issued = issue_invite(
        db,
        tenant_id=principal.tenant_id,
        email=email,
        role=body.role,
        invited_by_user_id=principal.user.id,
    )

    rendered = render_invite_email(
        to=email,
        token=issued.raw,
        firm_name=principal.tenant.name if principal.tenant else "your firm",
        role=body.role.value,
        inviter_name=principal.user.full_name,
    )
    send_email(
        to=email,
        subject=rendered.subject,
        text=rendered.text,
        html=rendered.html,
    )

    audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user.id,
        action="team.invite_sent",
        target_type="invite",
        target_id=str(issued.record.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        extra_metadata={"invitee": email, "role": body.role.value},
    )
    return InviteRead.model_validate(issued.record)


@router.delete(
    "/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def revoke_invite(
    invite_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    invite = db.execute(
        select(TenantInvite).where(
            TenantInvite.id == invite_id,
            TenantInvite.tenant_id == principal.tenant_id,
        )
    ).scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found.")
    if invite.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite already accepted.",
        )
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(timezone.utc)
        db.commit()
    audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user.id,
        action="team.invite_revoked",
        target_type="invite",
        target_id=str(invite.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
