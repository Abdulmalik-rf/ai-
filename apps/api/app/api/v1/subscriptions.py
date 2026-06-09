"""Subscription management for the current tenant.

  GET    /v1/subscriptions/me          — current subscription (plan + status + period)
  GET    /v1/subscriptions/usage       — current period usage vs caps (dashboard widget)
  POST   /v1/subscriptions/checkout    — start a new subscription (first time)
  POST   /v1/subscriptions/change-plan — switch tier (upgrade/downgrade)
  POST   /v1/subscriptions/cancel      — cancel current subscription

For a tenant browsing pricing, the typical flow is:
  1. GET /v1/plans                                 → see available tiers
  2. POST /v1/subscriptions/checkout {plan_tier}   → start payment
  3. (provider webhook flips status to ACTIVE)
  4. GET /v1/subscriptions/usage                   → confirm cap headroom

A `seats` metric is rendered alongside the message/document/contract counters
so admins can see "8 of 10 seats used" in the same widget.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal, require_role
from app.core.security import Role
from app.db.session import get_db
from app.models import Plan, Subscription, SubscriptionStatus, UsageEvent, User
from app.schemas.subscription import (
    ChangePlanRequest,
    CheckoutRequest,
    CheckoutResponse,
    SubscriptionRead,
    UsageMetric,
    UsageRead,
)
from app.services.billing import cancel_subscription, start_checkout

router = APIRouter()


# =============================================================================
# Read
# =============================================================================


@router.get("/me", response_model=SubscriptionRead | None)
def my_subscription(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> SubscriptionRead | None:
    sub = db.execute(
        select(Subscription).where(Subscription.tenant_id == principal.tenant_id)
    ).scalar_one_or_none()
    return SubscriptionRead.model_validate(sub) if sub else None


@router.get("/usage", response_model=UsageRead)
def usage(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> UsageRead:
    """Current month's usage vs the active plan's caps.

    The dashboard renders this as a small widget — bars + percentages — so
    admins can see when they're approaching upgrade territory.
    """
    sub_row = db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.tenant_id == principal.tenant_id)
    ).first()

    plan: Plan | None = None
    sub: Subscription | None = None
    if sub_row:
        sub, plan = sub_row

    period_start = _start_of_period()
    period_end = sub.current_period_end if sub else None

    metrics: list[UsageMetric] = []

    # Aggregate usage_events for the current period.
    rows = db.execute(
        select(UsageEvent.kind, func.coalesce(func.sum(UsageEvent.quantity), 0))
        .where(UsageEvent.tenant_id == principal.tenant_id)
        .where(UsageEvent.created_at >= period_start)
        .group_by(UsageEvent.kind)
    ).all()
    used_by_kind: dict[str, int] = {kind: int(total or 0) for kind, total in rows}

    cap_for = {
        "message": plan.monthly_messages_limit if plan else 0,
        "document_upload": plan.monthly_documents_limit if plan else 0,
        "contract_review": plan.monthly_contracts_limit if plan else 0,
    }
    for kind, cap in cap_for.items():
        used = used_by_kind.get(kind, 0)
        metrics.append(_build_metric(kind=kind, used=used, limit=cap))

    # Seats — always shown, computed live (not from usage_events).
    active_users = (
        db.execute(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == principal.tenant_id)
            .where(User.is_active.is_(True))
        ).scalar_one()
        or 0
    )
    metrics.append(
        _build_metric(
            kind="seats", used=int(active_users), limit=plan.seats_limit if plan else 0
        )
    )

    return UsageRead(
        plan_tier=plan.tier if plan else None,
        plan_name_en=plan.name_en if plan else None,
        plan_name_ar=plan.name_ar if plan else None,
        status=str(sub.status) if sub else None,
        period_start=period_start,
        period_end=period_end,
        metrics=metrics,
    )


# =============================================================================
# Mutations
# =============================================================================


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    body: CheckoutRequest,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> CheckoutResponse:
    url, session_id = start_checkout(
        db,
        tenant=principal.tenant,  # type: ignore[arg-type]
        plan_tier=body.plan_tier,
        provider=body.provider,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return CheckoutResponse(checkout_url=url, provider_session_id=session_id)


@router.post("/change-plan", response_model=CheckoutResponse)
def change_plan(
    body: ChangePlanRequest,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> CheckoutResponse:
    """Upgrade or downgrade the tenant's plan.

    Currently routed through the same checkout flow as /checkout so the
    user re-confirms the new price with the provider. Before redirecting
    we verify the new plan can hold the firm's current seat count —
    otherwise we refuse so admins don't accidentally lock teammates out.
    """
    target_plan = db.execute(
        select(Plan).where(Plan.tier == body.plan_tier, Plan.is_active.is_(True))
    ).scalar_one_or_none()
    if target_plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")

    # Refuse if a downgrade would push the firm over the new seat cap.
    active_seats = (
        db.execute(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == principal.tenant_id)
            .where(User.is_active.is_(True))
        ).scalar_one()
        or 0
    )
    if (
        target_plan.seats_limit
        and target_plan.seats_limit > 0
        and int(active_seats) > target_plan.seats_limit
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Your firm has {active_seats} active members but the "
                f"'{target_plan.tier.value}' plan allows {target_plan.seats_limit}. "
                "Deactivate members first."
            ),
        )

    url, session_id = start_checkout(
        db,
        tenant=principal.tenant,  # type: ignore[arg-type]
        plan_tier=body.plan_tier,
        provider=body.provider,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return CheckoutResponse(checkout_url=url, provider_session_id=session_id)


@router.post("/cancel", status_code=204, response_class=Response, response_model=None)
def cancel(
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    sub = db.execute(
        select(Subscription).where(Subscription.tenant_id == principal.tenant_id)
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="No active subscription.")
    cancel_subscription(db, subscription=sub)


# =============================================================================
# Helpers
# =============================================================================


def _start_of_period() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _build_metric(*, kind: str, used: int, limit: int) -> UsageMetric:
    if limit <= 0:
        return UsageMetric(kind=kind, used=used, limit=0, remaining=0, percentage=0.0)
    remaining = max(limit - used, 0)
    pct = min(used / limit, 1.0) if limit > 0 else 0.0
    return UsageMetric(
        kind=kind,
        used=used,
        limit=limit,
        remaining=remaining,
        percentage=round(pct, 4),
    )
