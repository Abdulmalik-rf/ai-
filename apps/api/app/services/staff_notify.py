"""Staff WhatsApp helpers.

Two responsibilities:

  1. **Normalise + sync allowlist.** When a staff member's phone number is
     set or updated, we normalise it to digits-only (matching the JID format
     the Baileys bridge surfaces) and upsert a row into
     `whatsapp_allowed_senders` for the tenant. Removing/changing a number
     prunes the old allowlist row so the staffer doesn't keep agent access
     after they've been removed.

  2. **Send task notifications.** Two flavours:
       - "You've been assigned a task" — fired immediately when a task is
         created with an assignee or when an existing task's assignee
         changes.
       - "Task due / overdue" — fired by a Celery beat sweep that runs
         every 15 minutes during the working day.

     Both calls are best-effort: bridge errors are logged and swallowed so
     a flaky WhatsApp connection never blocks a task write or breaks the
     beat sweep.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Task, User, WhatsAppAllowedSender, WhatsAppSession
from app.models.whatsapp import WhatsAppSessionStatus
from app.services.whatsapp_bridge import WhatsAppBridgeError, send_message

log = get_logger(__name__)


# =============================================================================
# Phone-number helpers
# =============================================================================


def normalize_phone(raw: str | None) -> str | None:
    """Strip whatsapp:, spaces, dashes, and the leading + so the value
    matches the JID format the Baileys bridge surfaces (digits only).

    Returns None if the result is empty or non-numeric so callers can treat
    "clearing the field" and "passing rubbish" the same way.
    """
    if not raw:
        return None
    s = raw.strip().replace("whatsapp:", "").replace(" ", "").replace("-", "")
    if s.startswith("+"):
        s = s[1:]
    if not s or not s.isdigit():
        return None
    return s


# =============================================================================
# Allowlist sync
# =============================================================================


def sync_user_allowlist(
    db: Session,
    *,
    user: User,
    previous_phone: str | None,
) -> None:
    """Reconcile the WhatsApp allowlist for one user.

    Compares the user's current `phone_number` against `previous_phone` and:
      - inserts an allowlist row for the new number (idempotent),
      - deletes the row for the old number if it changed and is no longer
        used by another staff member of this tenant.

    The caller commits the surrounding transaction; we only stage rows here.
    """
    if user.tenant_id is None:
        return  # super_admin or detached row — nothing to do

    new_phone = user.phone_number
    old_phone = normalize_phone(previous_phone) if previous_phone else None
    if new_phone == old_phone:
        return

    # Drop the stale allowlist row only if no *other* user on this tenant
    # is still using it.
    if old_phone:
        still_used = db.execute(
            select(User.id)
            .where(User.tenant_id == user.tenant_id)
            .where(User.id != user.id)
            .where(User.phone_number == old_phone)
        ).first()
        if still_used is None:
            stale = db.execute(
                select(WhatsAppAllowedSender).where(
                    WhatsAppAllowedSender.tenant_id == user.tenant_id,
                    WhatsAppAllowedSender.wa_phone == old_phone,
                )
            ).scalar_one_or_none()
            if stale is not None:
                db.delete(stale)

    # Upsert the new number.
    if new_phone:
        existing = db.execute(
            select(WhatsAppAllowedSender).where(
                WhatsAppAllowedSender.tenant_id == user.tenant_id,
                WhatsAppAllowedSender.wa_phone == new_phone,
            )
        ).scalar_one_or_none()
        if existing is None:
            row = WhatsAppAllowedSender(
                tenant_id=user.tenant_id,
                wa_phone=new_phone,
                label=user.full_name,
            )
            db.add(row)
        elif existing.label != user.full_name:
            existing.label = user.full_name


# =============================================================================
# Notification senders
# =============================================================================


def _session_is_connected(db: Session, tenant_id: UUID) -> bool:
    """Don't even try the bridge if we know the socket is disconnected."""
    if not settings.enable_whatsapp_baileys:
        return False
    session = db.execute(
        select(WhatsAppSession).where(WhatsAppSession.tenant_id == tenant_id)
    ).scalar_one_or_none()
    return bool(
        session is not None
        and session.status == WhatsAppSessionStatus.CONNECTED
    )


def _safe_send(*, tenant_id: UUID, to_phone: str, text: str, kind: str) -> bool:
    try:
        send_message(tenant_id=tenant_id, to_phone=to_phone, text=text)
        return True
    except WhatsAppBridgeError as exc:
        log.warning(
            "staff_notify_failed",
            kind=kind,
            tenant_id=str(tenant_id),
            error=str(exc),
        )
        return False


def _compose_assignment_text(task: Task, assignee: User) -> str:
    """The body of the "you've been assigned a task" WhatsApp message.

    Bilingual fallback: the AI agent will localise its tone elsewhere; here
    we send a clean Arabic body when the assignee's locale is Arabic,
    English otherwise.
    """
    if (assignee.locale or "ar").startswith("ar"):
        lines = [
            f"مرحبًا {assignee.full_name.split(' ')[0]} 👋",
            "تم تعيين مهمة جديدة لك:",
            f"• المهمة: {task.title}",
        ]
        if task.description:
            preview = task.description.strip()
            if len(preview) > 220:
                preview = preview[:220] + "…"
            lines.append(f"• الوصف: {preview}")
        if task.due_date:
            lines.append(f"• تاريخ الاستحقاق: {task.due_date.isoformat()}")
        lines.append(f"• الأولوية: {str(task.priority)}")
        lines.append("افتح لوحة التحكم لمراجعتها 💼")
        return "\n".join(lines)

    lines = [
        f"Hi {assignee.full_name.split(' ')[0]} 👋",
        "A new task has been assigned to you:",
        f"• Task: {task.title}",
    ]
    if task.description:
        preview = task.description.strip()
        if len(preview) > 220:
            preview = preview[:220] + "…"
        lines.append(f"• Details: {preview}")
    if task.due_date:
        lines.append(f"• Due: {task.due_date.isoformat()}")
    lines.append(f"• Priority: {str(task.priority)}")
    lines.append("Open the dashboard to review it.")
    return "\n".join(lines)


def _compose_due_reminder_text(task: Task, assignee: User, *, today: date) -> str:
    is_ar = (assignee.locale or "ar").startswith("ar")
    overdue = task.due_date is not None and task.due_date < today

    if is_ar:
        head = (
            f"⏰ تذكير: مهمة متأخرة" if overdue else f"⏰ تذكير: مهمة مستحقّة اليوم"
        )
        lines = [
            f"{head} — {assignee.full_name.split(' ')[0]}",
            f"• المهمة: {task.title}",
        ]
        if task.due_date:
            lines.append(f"• تاريخ الاستحقاق: {task.due_date.isoformat()}")
        lines.append(f"• الأولوية: {str(task.priority)}")
        return "\n".join(lines)

    head = "⏰ Reminder: task overdue" if overdue else "⏰ Reminder: task due today"
    lines = [
        f"{head} — {assignee.full_name.split(' ')[0]}",
        f"• Task: {task.title}",
    ]
    if task.due_date:
        lines.append(f"• Due: {task.due_date.isoformat()}")
    lines.append(f"• Priority: {str(task.priority)}")
    return "\n".join(lines)


def notify_task_assigned(db: Session, task: Task) -> None:
    """Send the assignee a WhatsApp message about a freshly-assigned task.

    Idempotent — checks `task.notified_at` to avoid double-sending when the
    assignee_id field hasn't changed between writes.
    """
    if not task.assignee_id:
        return
    assignee: User | None = db.get(User, task.assignee_id)
    if assignee is None or not assignee.phone_number:
        return
    if assignee.id == task.creator_id:
        # Don't ping yourself when you create a task you're assigning to
        # yourself — the dashboard already shows it.
        return
    if task.tenant_id is None:
        return
    if not _session_is_connected(db, task.tenant_id):
        return

    text = _compose_assignment_text(task, assignee)
    ok = _safe_send(
        tenant_id=task.tenant_id,
        to_phone=assignee.phone_number,
        text=text,
        kind="task_assigned",
    )
    if ok:
        task.notified_at = datetime.now(timezone.utc)


def notify_task_due(db: Session, task: Task, *, today: date) -> bool:
    """Send the assignee a "task due / overdue" reminder. Returns True on
    success so the caller can record the timestamp."""
    if not task.assignee_id:
        return False
    assignee: User | None = db.get(User, task.assignee_id)
    if assignee is None or not assignee.phone_number:
        return False
    if task.tenant_id is None:
        return False
    if not _session_is_connected(db, task.tenant_id):
        return False
    text = _compose_due_reminder_text(task, assignee, today=today)
    return _safe_send(
        tenant_id=task.tenant_id,
        to_phone=assignee.phone_number,
        text=text,
        kind="task_due",
    )
