"""Billing: Stripe (international) + Moyasar (Saudi Arabia).

The two providers are kept behind a single `start_checkout(...)` entry point.
Webhook handlers each translate provider events into our internal subscription
state machine (`SubscriptionStatus`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import httpx
import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models import (
    Plan,
    PlanTier,
    Subscription,
    SubscriptionStatus,
    Tenant,
    UsageEvent,
)

log = get_logger(__name__)

stripe.api_key = settings.stripe_secret_key


# ============================================================================
# Public entry points
# ============================================================================


def start_checkout(
    db: Session,
    *,
    tenant: Tenant,
    plan_tier: PlanTier,
    provider: str,
    success_url: str,
    cancel_url: str,
) -> tuple[str, str]:
    """Returns (checkout_url, provider_session_id)."""
    plan = db.execute(
        select(Plan).where(Plan.tier == plan_tier, Plan.is_active.is_(True))
    ).scalar_one_or_none()
    if plan is None:
        raise ValueError(f"Unknown plan tier: {plan_tier}")

    if provider == "stripe":
        return _stripe_checkout(db, tenant, plan, success_url, cancel_url)
    if provider == "moyasar":
        if not settings.enable_moyasar:
            raise ValueError("Moyasar disabled")
        return _moyasar_checkout(db, tenant, plan, success_url, cancel_url)
    raise ValueError(f"Unknown provider: {provider}")


def cancel_subscription(db: Session, *, subscription: Subscription) -> None:
    if subscription.provider == "stripe" and subscription.provider_subscription_id:
        stripe.Subscription.delete(subscription.provider_subscription_id)
    elif subscription.provider == "moyasar" and subscription.provider_subscription_id:
        _moyasar_cancel(subscription.provider_subscription_id)
    subscription.status = SubscriptionStatus.CANCELED
    db.add(subscription)
    db.commit()


# ============================================================================
# Stripe
# ============================================================================


def _stripe_checkout(
    db: Session,
    tenant: Tenant,
    plan: Plan,
    success_url: str,
    cancel_url: str,
) -> tuple[str, str]:
    if tenant.stripe_customer_id is None:
        customer = stripe.Customer.create(
            name=tenant.name, metadata={"tenant_id": str(tenant.id)}
        )
        tenant.stripe_customer_id = customer.id
        db.add(tenant)
        db.commit()

    if not plan.stripe_price_id:
        raise ValueError(f"Plan {plan.tier} has no Stripe price configured")

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=tenant.stripe_customer_id,
        line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"tenant_id": str(tenant.id), "plan_id": str(plan.id)},
        subscription_data={
            "metadata": {"tenant_id": str(tenant.id), "plan_id": str(plan.id)},
        },
    )
    return session.url or "", session.id


def handle_stripe_webhook(db: Session, payload: bytes, signature: str) -> None:
    event = stripe.Webhook.construct_event(
        payload, signature, settings.stripe_webhook_secret
    )
    etype = event["type"]
    obj = event["data"]["object"]
    log.info("stripe_webhook", type=etype)

    if etype == "checkout.session.completed":
        meta = obj.get("metadata") or {}
        tenant_id = meta.get("tenant_id")
        plan_id = meta.get("plan_id")
        provider_sub_id = obj.get("subscription")
        if not (tenant_id and plan_id and provider_sub_id):
            return
        _upsert_subscription(
            db,
            tenant_id=UUID(tenant_id),
            plan_id=UUID(plan_id),
            provider="stripe",
            provider_subscription_id=provider_sub_id,
            status=SubscriptionStatus.ACTIVE,
        )

    elif etype in {"customer.subscription.updated", "customer.subscription.created"}:
        meta = obj.get("metadata") or {}
        tenant_id = meta.get("tenant_id")
        plan_id = meta.get("plan_id")
        if not (tenant_id and plan_id):
            return
        status_map = {
            "trialing": SubscriptionStatus.TRIALING,
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "unpaid": SubscriptionStatus.PAST_DUE,
            "paused": SubscriptionStatus.PAUSED,
        }
        new_status = status_map.get(obj["status"], SubscriptionStatus.ACTIVE)
        _upsert_subscription(
            db,
            tenant_id=UUID(tenant_id),
            plan_id=UUID(plan_id),
            provider="stripe",
            provider_subscription_id=obj["id"],
            status=new_status,
            current_period_start=_ts(obj.get("current_period_start")),
            current_period_end=_ts(obj.get("current_period_end")),
        )

    elif etype == "customer.subscription.deleted":
        sub = db.execute(
            select(Subscription).where(Subscription.provider_subscription_id == obj["id"])
        ).scalar_one_or_none()
        if sub:
            sub.status = SubscriptionStatus.CANCELED
            db.add(sub)
            db.commit()


# ============================================================================
# Moyasar  (https://moyasar.com/docs/api/)
# ============================================================================


_MOYASAR_BASE = "https://api.moyasar.com/v1"


def _moyasar_checkout(
    db: Session,
    tenant: Tenant,
    plan: Plan,
    success_url: str,
    cancel_url: str,
) -> tuple[str, str]:
    """Moyasar uses an Invoice → hosted-payment URL flow for subscriptions.

    For recurring billing in production we'd run a scheduled job that creates
    a fresh invoice each period; for the initial checkout we create one here.
    """
    auth = (settings.moyasar_secret_key, "")
    payload = {
        "amount": plan.price_monthly_sar * 100,  # halalas
        "currency": "SAR",
        "description": f"{plan.name_en} — {tenant.name}",
        "callback_url": success_url,
        "back_url": cancel_url,
        "metadata": {
            "tenant_id": str(tenant.id),
            "plan_id": str(plan.id),
        },
    }
    with httpx.Client(timeout=15) as client:
        r = client.post(f"{_MOYASAR_BASE}/invoices", auth=auth, json=payload)
        r.raise_for_status()
        data = r.json()
    return data["url"], data["id"]


def _moyasar_cancel(provider_id: str) -> None:
    auth = (settings.moyasar_secret_key, "")
    with httpx.Client(timeout=15) as client:
        client.put(f"{_MOYASAR_BASE}/invoices/{provider_id}/cancel", auth=auth)


def handle_moyasar_webhook(db: Session, payload: dict) -> None:
    """Moyasar posts JSON; we look at `type` and `data`."""
    etype = payload.get("type")
    data = payload.get("data") or {}
    log.info("moyasar_webhook", type=etype)

    if etype == "payment_paid":
        meta = data.get("metadata") or {}
        tenant_id = meta.get("tenant_id")
        plan_id = meta.get("plan_id")
        if not (tenant_id and plan_id):
            return
        _upsert_subscription(
            db,
            tenant_id=UUID(tenant_id),
            plan_id=UUID(plan_id),
            provider="moyasar",
            provider_subscription_id=data.get("id", ""),
            status=SubscriptionStatus.ACTIVE,
        )

    elif etype == "payment_failed":
        meta = data.get("metadata") or {}
        tenant_id = meta.get("tenant_id")
        if tenant_id:
            sub = (
                db.query(Subscription)
                .filter(Subscription.tenant_id == UUID(tenant_id))
                .first()
            )
            if sub:
                sub.status = SubscriptionStatus.PAST_DUE
                db.add(sub)
                db.commit()


# ============================================================================
# Internal helpers
# ============================================================================


def _ts(value) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def _upsert_subscription(
    db: Session,
    *,
    tenant_id: UUID,
    plan_id: UUID,
    provider: str,
    provider_subscription_id: str,
    status: SubscriptionStatus,
    current_period_start: datetime | None = None,
    current_period_end: datetime | None = None,
) -> Subscription:
    existing = db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    ).scalar_one_or_none()

    if existing is None:
        existing = Subscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
            provider=provider,
            provider_subscription_id=provider_subscription_id,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
        )
    else:
        existing.plan_id = plan_id
        existing.provider = provider
        existing.provider_subscription_id = provider_subscription_id
        existing.status = status
        if current_period_start:
            existing.current_period_start = current_period_start
        if current_period_end:
            existing.current_period_end = current_period_end

    db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


# ============================================================================
# Trial provisioning (called on signup)
# ============================================================================


def start_trial_subscription(
    db: Session, *, tenant: Tenant, tier: PlanTier = PlanTier.BASIC
) -> Subscription | None:
    """Attach a TRIALING subscription to a freshly signed-up tenant.

    Idempotent — returns the existing row if one already exists. We default
    to BASIC so new firms can use the dashboard immediately without
    payment, then upgrade via /v1/subscriptions/checkout when they want
    higher caps.
    """
    existing = db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    plan = db.execute(
        select(Plan).where(Plan.tier == tier, Plan.is_active.is_(True))
    ).scalar_one_or_none()
    if plan is None:
        log.warning("trial_skip_no_plan", tier=tier.value)
        return None
    now = datetime.now(timezone.utc)
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status=SubscriptionStatus.TRIALING,
        provider="trial",
        current_period_start=now,
        current_period_end=now.replace(day=28),  # ~end of month sentinel
        trial_ends_at=now.replace(day=28),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ============================================================================
# Usage gating
# ============================================================================


class LimitExceeded(Exception):
    def __init__(self, kind: str, limit: int):
        self.kind = kind
        self.limit = limit
        super().__init__(f"limit_exceeded:{kind}:{limit}")


def record_usage(db: Session, *, tenant_id: UUID, kind: str, quantity: int = 1) -> None:
    db.add(UsageEvent(tenant_id=tenant_id, kind=kind, quantity=quantity))
    db.commit()


def assert_within_limits(db: Session, *, tenant_id: UUID, kind: str) -> None:
    """Throws `LimitExceeded` if the tenant has hit the cap for this period."""
    sub = db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.tenant_id == tenant_id)
    ).first()
    if sub is None:
        return  # Trial / unbilled — no enforcement here.

    _, plan = sub
    cap_field = {
        "message": plan.monthly_messages_limit,
        "document_upload": plan.monthly_documents_limit,
        "contract_review": plan.monthly_contracts_limit,
    }.get(kind)
    if cap_field is None or cap_field <= 0:
        return

    from sqlalchemy import func as _f  # local import to keep top clean

    used = (
        db.execute(
            select(_f.coalesce(_f.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.kind == kind,
                UsageEvent.created_at >= _start_of_period(),
            )
        ).scalar()
        or 0
    )
    if used >= cap_field:
        raise LimitExceeded(kind, cap_field)


def _start_of_period() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
