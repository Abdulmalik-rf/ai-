"""Lifecycle sweeps: billing dunning + PDPL purge.

Two daily Celery beat tasks:

  - run_billing_lifecycle_sweep: walks every Subscription, fires the right
    reminder/suspension when the trial or grace period passes.
  - run_pdpl_purge_sweep: hard-scrubs PII from any tenant or user whose
    `purge_at` has passed.

Tasks are idempotent — running them twice in a day is safe. Each branch
uses a marker on the row (or audit log) so we don't double-send the same
reminder.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import or_, select

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.metrics import billing_events_total
from app.db.session import SessionLocal
from app.models import (
    AgentFact,
    AuditLog,
    Case,
    Client,
    Conversation,
    Document,
    DocumentChunk,
    Message,
    Subscription,
    SubscriptionStatus,
    Task,
    TaskStatus,
    Tenant,
    TenantInvite,
    User,
    WhatsAppContact,
    WhatsAppEscalation,
    WhatsAppSession,
)
from app.services.audit import record as audit
from app.services.email import send_email
from app.services.staff_notify import notify_task_due
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# Billing lifecycle
# =============================================================================


@celery_app.task(name="app.workers.lifecycle.run_billing_lifecycle_sweep")
def run_billing_lifecycle_sweep() -> dict:
    """Walk subscriptions and apply the right action based on status + age.

    Transitions:
      - TRIALING with `trial_ends_at` < now → mark PAST_DUE + send reminder
      - PAST_DUE for {first/second}_reminder_days → resend reminder
      - PAST_DUE for >= suspend_after_days → mark CANCELED + suspend tenant
    """
    now = _now()
    summary = {"reminders": 0, "suspended": 0, "trial_expired": 0}

    db = SessionLocal()
    try:
        rows = list(
            db.execute(
                select(Subscription, Tenant)
                .join(Tenant, Tenant.id == Subscription.tenant_id)
                .where(
                    Subscription.status.in_(
                        [SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE]
                    )
                )
            ).all()
        )
        for sub, tenant in rows:
            try:
                summary = _process_one_subscription(db, sub, tenant, now, summary)
            except Exception:  # noqa: BLE001
                log.exception("lifecycle_one_failed", subscription_id=str(sub.id))
        db.commit()
    finally:
        db.close()
    log.info("billing_lifecycle_sweep_done", **summary)
    return summary


def _process_one_subscription(db, sub, tenant, now, summary):
    if sub.status == SubscriptionStatus.TRIALING:
        if sub.trial_ends_at and sub.trial_ends_at < now:
            sub.status = SubscriptionStatus.PAST_DUE
            summary["trial_expired"] += 1
            billing_events_total.labels(provider=sub.provider, event="trial_ended").inc()
            _send_dunning(tenant, kind="trial_ended")
            audit(
                db,
                tenant_id=tenant.id,
                actor_user_id=None,
                action="billing.trial_expired",
                target_type="subscription",
                target_id=str(sub.id),
            )
        return summary

    # PAST_DUE branch.
    days_overdue = (now - (sub.current_period_end or sub.updated_at)).days
    if days_overdue >= settings.dunning_suspend_after_days:
        sub.status = SubscriptionStatus.CANCELED
        tenant.is_active = False
        summary["suspended"] += 1
        billing_events_total.labels(provider=sub.provider, event="suspended").inc()
        _send_dunning(tenant, kind="suspended")
        audit(
            db,
            tenant_id=tenant.id,
            actor_user_id=None,
            action="billing.suspended",
            target_type="subscription",
            target_id=str(sub.id),
            extra_metadata={"days_overdue": days_overdue},
        )
        return summary

    if days_overdue >= settings.dunning_second_reminder_days:
        if not _already_sent(db, tenant.id, "billing.dunning_2"):
            _send_dunning(tenant, kind="reminder_2")
            summary["reminders"] += 1
            billing_events_total.labels(provider=sub.provider, event="dunning_2").inc()
            audit(
                db,
                tenant_id=tenant.id,
                actor_user_id=None,
                action="billing.dunning_2",
                target_type="subscription",
                target_id=str(sub.id),
            )
        return summary

    if days_overdue >= settings.dunning_first_reminder_days:
        if not _already_sent(db, tenant.id, "billing.dunning_1"):
            _send_dunning(tenant, kind="reminder_1")
            summary["reminders"] += 1
            billing_events_total.labels(provider=sub.provider, event="dunning_1").inc()
            audit(
                db,
                tenant_id=tenant.id,
                actor_user_id=None,
                action="billing.dunning_1",
                target_type="subscription",
                target_id=str(sub.id),
            )
    return summary


def _already_sent(db, tenant_id, action: str) -> bool:
    """Don't double-send the same reminder. Audit log is the source of truth."""
    return (
        db.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .where(AuditLog.action == action)
            .where(AuditLog.created_at > _now() - timedelta(days=2))
        ).scalar_one_or_none()
        is not None
    )


def _send_dunning(tenant: Tenant, *, kind: str) -> None:
    """Tiny email dispatcher for dunning + suspension notices."""
    to = tenant.billing_email
    if not to:
        log.warning(
            "dunning_no_billing_email", tenant_id=str(tenant.id), kind=kind
        )
        return
    if kind == "trial_ended":
        subject = "Your trial has ended — Legal AI OS / انتهت فترة التجربة"
        body = (
            f"Hi {tenant.name},\n\n"
            "Your free trial has ended. Add a payment method to keep using "
            "the dashboard and the WhatsApp agent. Visit "
            f"{settings.app_base_url}/billing to upgrade.\n\n"
            "—— Legal AI OS"
        )
    elif kind == "reminder_1":
        subject = "Payment due — Legal AI OS / استحقاق الدفع"
        body = (
            f"Hi {tenant.name},\n\nWe couldn't process your latest payment. "
            f"Please update your billing details at {settings.app_base_url}/billing "
            "within the next few days to avoid suspension."
        )
    elif kind == "reminder_2":
        subject = "Final notice — service will be paused / تنبيه أخير"
        body = (
            f"Hi {tenant.name},\n\nThis is the final notice before we pause "
            f"your account. Update billing at {settings.app_base_url}/billing now."
        )
    else:  # suspended
        subject = "Service paused — Legal AI OS / تم إيقاف الخدمة"
        body = (
            f"Hi {tenant.name},\n\nWe paused your account because the "
            "subscription remained unpaid. Re-activate any time at "
            f"{settings.app_base_url}/billing. Your data is safe and will be "
            "available immediately upon reactivation."
        )
    send_email(to=to, subject=subject, text=body)


# =============================================================================
# PDPL purge
# =============================================================================


@celery_app.task(name="app.workers.lifecycle.run_pdpl_purge_sweep")
def run_pdpl_purge_sweep() -> dict:
    """Hard-scrub PII for any tenant or user whose grace window has passed.

    For tenants: cascade-delete all owned business rows (cases, clients,
    documents, conversations, etc.) and zero out PII on the tenant row,
    keeping only the audit log linkage.

    For users: zero out PII on the user row (preserve ID for audit
    linkage), revoke sessions.
    """
    now = _now()
    summary = {"users_purged": 0, "tenants_purged": 0}

    db = SessionLocal()
    try:
        users = list(
            db.execute(
                select(User)
                .where(User.purge_at.is_not(None))
                .where(User.purge_at < now)
            ).scalars()
        )
        for u in users:
            try:
                _purge_user(db, u)
                summary["users_purged"] += 1
            except Exception:  # noqa: BLE001
                log.exception("user_purge_failed", user_id=str(u.id))

        tenants = list(
            db.execute(
                select(Tenant)
                .where(Tenant.purge_at.is_not(None))
                .where(Tenant.purge_at < now)
            ).scalars()
        )
        for t in tenants:
            try:
                _purge_tenant(db, t)
                summary["tenants_purged"] += 1
            except Exception:  # noqa: BLE001
                log.exception("tenant_purge_failed", tenant_id=str(t.id))
        db.commit()
    finally:
        db.close()
    log.info("pdpl_purge_sweep_done", **summary)
    return summary


def _purge_user(db, user: User) -> None:
    user.email = f"deleted-{user.id}@purged.invalid"
    user.full_name = "[deleted]"
    user.hashed_password = ""
    user.is_active = False
    user.purge_at = None
    user.deletion_scheduled_at = None
    audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=None,
        action="compliance.user_purged",
        target_type="user",
        target_id=str(user.id),
    )


def _purge_tenant(db, tenant: Tenant) -> None:
    """Cascade-delete business data for a tenant whose grace period has passed.

    Order matters because of FK dependencies. We rely on the ON DELETE CASCADE
    set on `tenant_id` columns where possible, but the tenant row itself
    stays — with PII scrubbed — so audit history retains its anchor.
    """
    tenant_id = tenant.id

    # Order: facts → escalations → conversations (cascades messages),
    # documents → cases → clients → contacts → sessions → invites.
    for model in (
        AgentFact,
        WhatsAppEscalation,
        Message,
        Conversation,
        DocumentChunk,
        Document,
        Case,
        Client,
        WhatsAppContact,
        WhatsAppSession,
        TenantInvite,
    ):
        rows = db.execute(
            select(model).where(model.tenant_id == tenant_id)
        ).scalars()
        for r in rows:
            db.delete(r)

    # Scrub the tenant row's PII.
    tenant.name = f"[purged-{tenant.id}]"
    tenant.billing_email = None
    tenant.billing_address = None
    tenant.vat_number = None
    tenant.is_active = False
    tenant.purge_at = None
    tenant.deletion_scheduled_at = None

    audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=None,
        action="compliance.tenant_purged",
        target_type="tenant",
        target_id=str(tenant_id),
    )


# =============================================================================
# Task due-date reminder sweep
# =============================================================================


@celery_app.task(name="app.workers.lifecycle.run_task_reminder_sweep")
def run_task_reminder_sweep() -> dict:
    """Walk open tasks whose due_date has arrived (or passed) and send the
    assignee a WhatsApp reminder.

    Idempotent: each task carries `due_reminder_sent_at`, so we never
    notify the same task twice unless an admin clears the timestamp.
    """
    today = _now().astimezone().date()
    summary = {"reminded": 0, "skipped_no_assignee": 0, "skipped_no_phone": 0}

    db = SessionLocal()
    try:
        rows = list(
            db.execute(
                select(Task)
                .where(
                    Task.status.in_(
                        [
                            TaskStatus.OPEN,
                            TaskStatus.IN_PROGRESS,
                            TaskStatus.BLOCKED,
                        ]
                    )
                )
                .where(Task.due_date.is_not(None))
                .where(Task.due_date <= today)
                .where(Task.due_reminder_sent_at.is_(None))
                .where(Task.assignee_id.is_not(None))
            ).scalars()
        )
        for task in rows:
            ok = notify_task_due(db, task, today=today)
            if ok:
                task.due_reminder_sent_at = _now()
                summary["reminded"] += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    log.info("task_reminder_sweep", **summary)
    return summary
