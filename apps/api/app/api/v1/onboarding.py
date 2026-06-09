"""Onboarding tracker — drives the post-signup wizard.

Each tenant has a JSON state blob on `tenants.onboarding_state` listing
which steps they've completed. The dashboard reads this and renders the
right next-step prompt.

Step taxonomy:
  - email_verified        → user confirmed their email
  - team_invited          → ≥1 invite issued
  - whatsapp_paired       → bridge has reported `connected`
  - first_document        → ≥1 indexed document for this tenant
  - agent_profile_set     → AgentProfile exists + has any custom field
  - plan_chosen           → subscription is not the default trial

The router exposes:
  GET   /v1/onboarding/status  — full state + next recommended step
  POST  /v1/onboarding/skip    — admin marks the wizard complete
  POST  /v1/onboarding/refresh — recompute state from live data (idempotent)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal, require_role
from app.core.security import Role
from app.db.session import get_db
from app.models import (
    AgentProfile,
    Document,
    DocumentStatus,
    Subscription,
    SubscriptionStatus,
    TenantInvite,
    User,
    WhatsAppSession,
    WhatsAppSessionStatus,
)

router = APIRouter()


# Canonical step list — keep this in sync with the dashboard wizard so the
# next-step suggestion is meaningful.
STEPS = (
    "email_verified",
    "team_invited",
    "whatsapp_paired",
    "first_document",
    "agent_profile_set",
    "plan_chosen",
)


class OnboardingStatus(BaseModel):
    completed: dict[str, bool]
    next_step: str | None
    progress: float  # 0.0 - 1.0
    completed_at: datetime | None


def _compute_state(db: Session, *, tenant_id, user_email: str) -> dict[str, bool]:
    """Recompute every step from live data. Cheap (≤6 small queries)."""
    state: dict[str, bool] = {s: False for s in STEPS}

    # email_verified — any active user in the tenant who's verified.
    state["email_verified"] = (
        db.execute(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == tenant_id)
            .where(User.is_email_verified.is_(True))
        ).scalar_one()
        or 0
    ) > 0

    state["team_invited"] = (
        db.execute(
            select(func.count())
            .select_from(TenantInvite)
            .where(TenantInvite.tenant_id == tenant_id)
        ).scalar_one()
        or 0
    ) > 0

    sess = db.execute(
        select(WhatsAppSession).where(WhatsAppSession.tenant_id == tenant_id)
    ).scalar_one_or_none()
    state["whatsapp_paired"] = (
        sess is not None and sess.status == WhatsAppSessionStatus.CONNECTED
    )

    state["first_document"] = (
        db.execute(
            select(func.count())
            .select_from(Document)
            .where(Document.tenant_id == tenant_id)
            .where(Document.status == DocumentStatus.INDEXED)
        ).scalar_one()
        or 0
    ) > 0

    profile = db.execute(
        select(AgentProfile).where(AgentProfile.tenant_id == tenant_id)
    ).scalar_one_or_none()
    state["agent_profile_set"] = profile is not None and any(
        getattr(profile, f, None)
        for f in (
            "firm_specialties",
            "consultation_offer",
            "tone_guidelines",
            "custom_instructions",
            "welcome_message_ar",
            "welcome_message_en",
        )
    )

    sub = db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    ).scalar_one_or_none()
    state["plan_chosen"] = (
        sub is not None
        and sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)
        and sub.provider != "trial"
    )

    return state


def _next_step(state: dict[str, bool]) -> str | None:
    for s in STEPS:
        if not state.get(s):
            return s
    return None


@router.get("/status", response_model=OnboardingStatus)
def status_(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingStatus:
    if principal.tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required."
        )
    tenant = principal.tenant
    state = _compute_state(
        db, tenant_id=tenant.id, user_email=principal.user.email
    )
    # Persist the recomputed snapshot so the dashboard can read it back fast.
    tenant.onboarding_state = state
    next_s = _next_step(state)
    if next_s is None and tenant.onboarding_completed_at is None:
        tenant.onboarding_completed_at = datetime.now(timezone.utc)
    db.commit()

    completed = sum(1 for v in state.values() if v)
    return OnboardingStatus(
        completed=state,
        next_step=next_s,
        progress=completed / len(STEPS),
        completed_at=tenant.onboarding_completed_at,
    )


@router.post("/skip", response_model=OnboardingStatus)
def skip(
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingStatus:
    """Admin override — mark the wizard complete without finishing all steps."""
    tenant = principal.tenant
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context required."
        )
    tenant.onboarding_completed_at = datetime.now(timezone.utc)
    db.commit()
    return status_(principal, db)


@router.post("/refresh", response_model=OnboardingStatus)
def refresh(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingStatus:
    """Force a recompute. Same as /status — kept as a separate POST so the
    dashboard's 'Recheck' button feels intentional."""
    return status_(principal, db)
