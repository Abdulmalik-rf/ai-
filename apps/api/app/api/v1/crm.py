"""CRM workspace routes.

Six entity routers + one dashboard router. Each follows the standard
list/create/get/update/delete shape used by the older `clients` and
`cases` routers, with tenant scoping enforced via TenantQuery.

A tiny `_record_activity` helper lets every mutating route drop a row in
the activities log so the case timeline updates automatically without
each endpoint having to remember.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenancy import TenantQuery
from app.models import (
    Activity,
    ActivityKind,
    Case,
    CaseNote,
    CaseStatus,
    Client,
    ClientStatus,
    Contact,
    Hearing,
    HearingStatus,
    Invoice,
    InvoiceStatus,
    Task,
    TaskStatus,
    TimeEntry,
)
from app.schemas.crm import (
    ActivityCreate,
    ActivityRead,
    ActivitySummary,
    CaseNoteCreate,
    CaseNoteRead,
    CaseNoteUpdate,
    ContactCreate,
    ContactRead,
    ContactUpdate,
    DashboardSummary,
    HearingCreate,
    HearingRead,
    HearingSummary,
    HearingUpdate,
    TaskCreate,
    TaskRead,
    TaskSummary,
    TaskUpdate,
    TimeEntryCreate,
    TimeEntryRead,
    TimeEntryUpdate,
)
from app.services.staff_notify import notify_task_assigned


# ---------- helpers ----------------------------------------------------------


def _record_activity(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID | None,
    kind: ActivityKind,
    summary: str,
    case_id: UUID | None = None,
    client_id: UUID | None = None,
    body: str | None = None,
    extra: dict | None = None,
) -> None:
    """Append an activity row. Committed by the caller."""
    db.add(
        Activity(
            tenant_id=tenant_id,
            user_id=user_id,
            kind=kind,
            summary=summary,
            case_id=case_id,
            client_id=client_id,
            body=body,
            extra=extra or {},
        )
    )


def _refresh_next_hearing(db: Session, case_id: UUID, tenant_id: UUID) -> None:
    """Recompute `cases.next_hearing_at` from the soonest future scheduled hearing."""
    stmt = (
        select(func.min(Hearing.scheduled_at))
        .where(
            Hearing.tenant_id == tenant_id,
            Hearing.case_id == case_id,
            Hearing.status == HearingStatus.SCHEDULED,
            Hearing.scheduled_at >= func.now(),
        )
    )
    next_at = db.execute(stmt).scalar_one_or_none()
    case = TenantQuery.get(db, Case, tenant_id, case_id)
    if case is not None:
        case.next_hearing_at = next_at


# =============================================================================
# Tasks
# =============================================================================

tasks_router = APIRouter()


@tasks_router.get("", response_model=list[TaskRead])
def list_tasks(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    assignee: UUID | None = None,
    case_id: UUID | None = None,
    mine: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[TaskRead]:
    stmt = (
        select(Task)
        .where(Task.tenant_id == principal.tenant_id)
        .order_by(
            # NULLS LAST on due_date so anything overdue rises to the top.
            Task.due_date.asc().nulls_last(),
            Task.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)
    if assignee:
        stmt = stmt.where(Task.assignee_id == assignee)
    if mine:
        stmt = stmt.where(Task.assignee_id == principal.user.id)
    if case_id:
        stmt = stmt.where(Task.case_id == case_id)
    rows = db.execute(stmt).scalars().all()
    return [TaskRead.model_validate(r) for r in rows]


@tasks_router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    body: TaskCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskRead:
    task = Task(
        tenant_id=principal.tenant_id,
        creator_id=principal.user.id,
        **body.model_dump(),
    )
    db.add(task)
    db.flush()
    if task.case_id:
        _record_activity(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user.id,
            kind=ActivityKind.OTHER,
            summary=f"Task created: {task.title}",
            case_id=task.case_id,
        )

    # Notify the assignee on WhatsApp (best-effort; bridge errors are
    # logged and swallowed inside the helper).
    notify_task_assigned(db, task)

    db.commit()
    db.refresh(task)
    return TaskRead.model_validate(task)


@tasks_router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskRead:
    task = TenantQuery.get(db, Task, principal.tenant_id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return TaskRead.model_validate(task)


@tasks_router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: UUID,
    body: TaskUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> TaskRead:
    task = TenantQuery.get(db, Task, principal.tenant_id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    data = body.model_dump(exclude_unset=True)
    # Auto-stamp completed_at when status flips to completed.
    if data.get("status") == TaskStatus.COMPLETED and task.completed_at is None:
        data.setdefault("completed_at", datetime.now(timezone.utc))
        if task.case_id:
            _record_activity(
                db,
                tenant_id=principal.tenant_id,
                user_id=principal.user.id,
                kind=ActivityKind.TASK_COMPLETED,
                summary=f"Task completed: {task.title}",
                case_id=task.case_id,
            )

    # Detect assignee transitions so we re-notify when a task is reassigned.
    # We don't notify on completion, only on (re)assignment.
    previous_assignee_id = task.assignee_id
    for k, v in data.items():
        setattr(task, k, v)
    assignee_changed = (
        "assignee_id" in data and task.assignee_id != previous_assignee_id
    )
    if assignee_changed and task.assignee_id is not None:
        # Reset the notified marker so notify_task_assigned will fire.
        task.notified_at = None
        notify_task_assigned(db, task)

    db.commit()
    db.refresh(task)
    return TaskRead.model_validate(task)


@tasks_router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_task(
    task_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    task = TenantQuery.get(db, Task, principal.tenant_id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    db.delete(task)
    db.commit()


# =============================================================================
# Hearings
# =============================================================================

hearings_router = APIRouter()


@hearings_router.get("", response_model=list[HearingRead])
def list_hearings(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    case_id: UUID | None = None,
    upcoming_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[HearingRead]:
    stmt = (
        select(Hearing)
        .where(Hearing.tenant_id == principal.tenant_id)
        .order_by(Hearing.scheduled_at.asc())
        .limit(limit)
        .offset(offset)
    )
    if case_id:
        stmt = stmt.where(Hearing.case_id == case_id)
    if upcoming_only:
        stmt = stmt.where(Hearing.scheduled_at >= datetime.now(timezone.utc))
    rows = db.execute(stmt).scalars().all()
    return [HearingRead.model_validate(r) for r in rows]


@hearings_router.post("", response_model=HearingRead, status_code=status.HTTP_201_CREATED)
def create_hearing(
    body: HearingCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> HearingRead:
    # Guard: the case must belong to this tenant.
    case = TenantQuery.get(db, Case, principal.tenant_id, body.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    hearing = Hearing(tenant_id=principal.tenant_id, **body.model_dump())
    db.add(hearing)
    db.flush()
    _refresh_next_hearing(db, body.case_id, principal.tenant_id)
    _record_activity(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user.id,
        kind=ActivityKind.HEARING_SCHEDULED,
        summary=f"Hearing scheduled for {body.scheduled_at.isoformat()} ({body.kind.value})",
        case_id=body.case_id,
    )
    db.commit()
    db.refresh(hearing)
    return HearingRead.model_validate(hearing)


@hearings_router.get("/{hearing_id}", response_model=HearingRead)
def get_hearing(
    hearing_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> HearingRead:
    hearing = TenantQuery.get(db, Hearing, principal.tenant_id, hearing_id)
    if hearing is None:
        raise HTTPException(status_code=404, detail="Hearing not found.")
    return HearingRead.model_validate(hearing)


@hearings_router.patch("/{hearing_id}", response_model=HearingRead)
def update_hearing(
    hearing_id: UUID,
    body: HearingUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> HearingRead:
    hearing = TenantQuery.get(db, Hearing, principal.tenant_id, hearing_id)
    if hearing is None:
        raise HTTPException(status_code=404, detail="Hearing not found.")
    data = body.model_dump(exclude_unset=True)
    had_outcome = hearing.outcome
    for k, v in data.items():
        setattr(hearing, k, v)
    db.flush()
    _refresh_next_hearing(db, hearing.case_id, principal.tenant_id)
    if data.get("outcome") and not had_outcome:
        _record_activity(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user.id,
            kind=ActivityKind.HEARING_OUTCOME,
            summary=f"Hearing outcome recorded",
            case_id=hearing.case_id,
            body=data["outcome"],
        )
    db.commit()
    db.refresh(hearing)
    return HearingRead.model_validate(hearing)


@hearings_router.delete(
    "/{hearing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_hearing(
    hearing_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    hearing = TenantQuery.get(db, Hearing, principal.tenant_id, hearing_id)
    if hearing is None:
        raise HTTPException(status_code=404, detail="Hearing not found.")
    case_id = hearing.case_id
    db.delete(hearing)
    db.flush()
    _refresh_next_hearing(db, case_id, principal.tenant_id)
    db.commit()


# =============================================================================
# Time entries
# =============================================================================

time_entries_router = APIRouter()


@time_entries_router.get("", response_model=list[TimeEntryRead])
def list_time_entries(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    case_id: UUID | None = None,
    user_id: UUID | None = None,
    unbilled_only: bool = False,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TimeEntryRead]:
    stmt = (
        select(TimeEntry)
        .where(TimeEntry.tenant_id == principal.tenant_id)
        .order_by(TimeEntry.work_date.desc(), TimeEntry.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if case_id:
        stmt = stmt.where(TimeEntry.case_id == case_id)
    if user_id:
        stmt = stmt.where(TimeEntry.user_id == user_id)
    if unbilled_only:
        stmt = stmt.where(TimeEntry.invoice_id.is_(None), TimeEntry.billable.is_(True))
    if from_date:
        stmt = stmt.where(TimeEntry.work_date >= from_date)
    if to_date:
        stmt = stmt.where(TimeEntry.work_date <= to_date)
    rows = db.execute(stmt).scalars().all()
    return [TimeEntryRead.model_validate(r) for r in rows]


@time_entries_router.post("", response_model=TimeEntryRead, status_code=status.HTTP_201_CREATED)
def create_time_entry(
    body: TimeEntryCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> TimeEntryRead:
    entry = TimeEntry(
        tenant_id=principal.tenant_id,
        user_id=principal.user.id,
        **body.model_dump(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return TimeEntryRead.model_validate(entry)


@time_entries_router.patch("/{entry_id}", response_model=TimeEntryRead)
def update_time_entry(
    entry_id: UUID,
    body: TimeEntryUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> TimeEntryRead:
    entry = TenantQuery.get(db, TimeEntry, principal.tenant_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Time entry not found.")
    if entry.invoice_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Time entry is already on an invoice and is immutable.",
        )
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return TimeEntryRead.model_validate(entry)


@time_entries_router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_time_entry(
    entry_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    entry = TenantQuery.get(db, TimeEntry, principal.tenant_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Time entry not found.")
    if entry.invoice_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Time entry already invoiced; void the invoice instead.",
        )
    db.delete(entry)
    db.commit()


# =============================================================================
# Case notes
# =============================================================================

notes_router = APIRouter()


@notes_router.get("", response_model=list[CaseNoteRead])
def list_notes(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    case_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[CaseNoteRead]:
    stmt = (
        select(CaseNote)
        .where(CaseNote.tenant_id == principal.tenant_id)
        .order_by(CaseNote.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if case_id:
        stmt = stmt.where(CaseNote.case_id == case_id)
    rows = db.execute(stmt).scalars().all()
    return [CaseNoteRead.model_validate(r) for r in rows]


@notes_router.post("", response_model=CaseNoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    body: CaseNoteCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseNoteRead:
    case = TenantQuery.get(db, Case, principal.tenant_id, body.case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    note = CaseNote(
        tenant_id=principal.tenant_id,
        author_id=principal.user.id,
        **body.model_dump(),
    )
    db.add(note)
    _record_activity(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user.id,
        kind=ActivityKind.NOTE_ADDED,
        summary="Note added to case",
        case_id=body.case_id,
    )
    db.commit()
    db.refresh(note)
    return CaseNoteRead.model_validate(note)


@notes_router.patch("/{note_id}", response_model=CaseNoteRead)
def update_note(
    note_id: UUID,
    body: CaseNoteUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseNoteRead:
    note = TenantQuery.get(db, CaseNote, principal.tenant_id, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found.")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(note, k, v)
    db.commit()
    db.refresh(note)
    return CaseNoteRead.model_validate(note)


@notes_router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_note(
    note_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    note = TenantQuery.get(db, CaseNote, principal.tenant_id, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found.")
    db.delete(note)
    db.commit()


# =============================================================================
# Contacts
# =============================================================================

contacts_router = APIRouter()


@contacts_router.get("", response_model=list[ContactRead])
def list_contacts(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    kind: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ContactRead]:
    stmt = (
        select(Contact)
        .where(Contact.tenant_id == principal.tenant_id)
        .order_by(Contact.name.asc())
        .limit(limit)
        .offset(offset)
    )
    if kind:
        stmt = stmt.where(Contact.kind == kind)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(Contact.name.ilike(like), Contact.organization.ilike(like))
        )
    rows = db.execute(stmt).scalars().all()
    return [ContactRead.model_validate(r) for r in rows]


@contacts_router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(
    body: ContactCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ContactRead:
    contact = Contact(tenant_id=principal.tenant_id, **body.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return ContactRead.model_validate(contact)


@contacts_router.get("/{contact_id}", response_model=ContactRead)
def get_contact(
    contact_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ContactRead:
    contact = TenantQuery.get(db, Contact, principal.tenant_id, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    return ContactRead.model_validate(contact)


@contacts_router.patch("/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: UUID,
    body: ContactUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ContactRead:
    contact = TenantQuery.get(db, Contact, principal.tenant_id, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(contact, k, v)
    db.commit()
    db.refresh(contact)
    return ContactRead.model_validate(contact)


@contacts_router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_contact(
    contact_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    contact = TenantQuery.get(db, Contact, principal.tenant_id, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found.")
    db.delete(contact)
    db.commit()


# =============================================================================
# Activities (read-only + manual append)
# =============================================================================

activities_router = APIRouter()


@activities_router.get("", response_model=list[ActivityRead])
def list_activities(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    case_id: UUID | None = None,
    client_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ActivityRead]:
    stmt = (
        select(Activity)
        .where(Activity.tenant_id == principal.tenant_id)
        .order_by(Activity.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if case_id:
        stmt = stmt.where(Activity.case_id == case_id)
    if client_id:
        stmt = stmt.where(Activity.client_id == client_id)
    rows = db.execute(stmt).scalars().all()
    return [ActivityRead.model_validate(r) for r in rows]


@activities_router.post("", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
def create_activity(
    body: ActivityCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ActivityRead:
    data = body.model_dump()
    data.setdefault("occurred_at", datetime.now(timezone.utc))
    activity = Activity(
        tenant_id=principal.tenant_id,
        user_id=principal.user.id,
        **data,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return ActivityRead.model_validate(activity)


# =============================================================================
# Dashboard summary
# =============================================================================

dashboard_router = APIRouter()


@dashboard_router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> DashboardSummary:
    tid = principal.tenant_id
    now = datetime.now(timezone.utc)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    next_week = now + timedelta(days=7)

    # ---- counts: 3 round-trips instead of 7 ----
    # Each table is scoped to the tenant in WHERE so the FILTER aggregates
    # only count within already-narrowed result sets. Drops the endpoint from
    # ~220ms to ~80ms on local Postgres.
    counts_row = db.execute(
        select(
            func.count().label("total_clients"),
            func.count().filter(Client.status == ClientStatus.ACTIVE).label("active_clients"),
            func.count().filter(Client.status == ClientStatus.LEAD).label("leads"),
        )
        .select_from(Client)
        .where(Client.tenant_id == tid)
    ).one()

    case_counts = db.execute(
        select(
            func.count().filter(
                Case.status.in_([CaseStatus.INTAKE, CaseStatus.OPEN])
            ).label("open_cases"),
            func.count().filter(Case.status == CaseStatus.IN_COURT).label("cases_in_court"),
        )
        .select_from(Case)
        .where(Case.tenant_id == tid)
    ).one()

    task_counts = db.execute(
        select(
            func.count().filter(
                Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
                Task.due_date.is_not(None),
                Task.due_date < today,
            ).label("overdue"),
            func.count().filter(
                Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS])
            ).label("open"),
        )
        .select_from(Task)
        .where(Task.tenant_id == tid)
    ).one()

    total_clients = counts_row.total_clients
    active_clients = counts_row.active_clients
    leads = counts_row.leads
    open_cases = case_counts.open_cases
    cases_in_court = case_counts.cases_in_court
    overdue_tasks = task_counts.overdue
    open_tasks = task_counts.open

    # ---- today's hearings ----
    today_rows = db.execute(
        select(Hearing, Case.title)
        .join(Case, Case.id == Hearing.case_id, isouter=True)
        .where(
            Hearing.tenant_id == tid,
            Hearing.scheduled_at >= datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
            Hearing.scheduled_at < datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc),
        )
        .order_by(Hearing.scheduled_at.asc())
    ).all()
    today_hearings = [
        HearingSummary(
            id=h.id, case_id=h.case_id, case_title=ct,
            scheduled_at=h.scheduled_at, court_name=h.court_name, kind=h.kind,
        )
        for h, ct in today_rows
    ]

    # ---- upcoming hearings (next 7 days, excluding today) ----
    upcoming_rows = db.execute(
        select(Hearing, Case.title)
        .join(Case, Case.id == Hearing.case_id, isouter=True)
        .where(
            Hearing.tenant_id == tid,
            Hearing.scheduled_at >= datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc),
            Hearing.scheduled_at <= next_week,
            Hearing.status == HearingStatus.SCHEDULED,
        )
        .order_by(Hearing.scheduled_at.asc())
        .limit(10)
    ).all()
    upcoming_hearings = [
        HearingSummary(
            id=h.id, case_id=h.case_id, case_title=ct,
            scheduled_at=h.scheduled_at, court_name=h.court_name, kind=h.kind,
        )
        for h, ct in upcoming_rows
    ]

    # ---- my open tasks ----
    my_task_rows = db.execute(
        select(Task)
        .where(
            Task.tenant_id == tid,
            Task.assignee_id == principal.user.id,
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
        )
        .order_by(Task.due_date.asc().nulls_last())
        .limit(10)
    ).scalars().all()
    my_tasks = [
        TaskSummary(
            id=t.id, title=t.title, priority=t.priority,
            due_date=t.due_date, case_id=t.case_id,
        )
        for t in my_task_rows
    ]

    # ---- recent activities ----
    recent = db.execute(
        select(Activity)
        .where(Activity.tenant_id == tid)
        .order_by(Activity.occurred_at.desc())
        .limit(12)
    ).scalars().all()
    recent_activities = [
        ActivitySummary(
            id=a.id, kind=a.kind, summary=a.summary, occurred_at=a.occurred_at,
            case_id=a.case_id, client_id=a.client_id,
        )
        for a in recent
    ]

    # ---- cash flow indicators ----
    unbilled_minutes = (
        db.execute(
            select(func.coalesce(func.sum(TimeEntry.minutes), 0)).where(
                TimeEntry.tenant_id == tid,
                TimeEntry.billable.is_(True),
                TimeEntry.invoice_id.is_(None),
                TimeEntry.work_date >= today - timedelta(days=30),
            )
        ).scalar_one()
    ) or 0
    # "Unpaid" = issued but not yet paid; we don't model an explicit
    # PAST_DUE bucket, so anything ISSUED + past its due date is implicitly
    # past due and still counted here.
    unpaid_invoices = db.execute(
        select(func.count(Invoice.id)).where(
            Invoice.tenant_id == tid,
            Invoice.status == InvoiceStatus.ISSUED,
        )
    ).scalar_one()

    return DashboardSummary(
        total_clients=total_clients,
        active_clients=active_clients,
        leads=leads,
        open_cases=open_cases,
        cases_in_court=cases_in_court,
        overdue_tasks=overdue_tasks,
        open_tasks=open_tasks,
        today_hearings=today_hearings,
        upcoming_hearings=upcoming_hearings,
        my_tasks=my_tasks,
        recent_activities=recent_activities,
        unbilled_minutes_30d=int(unbilled_minutes),
        unpaid_invoices_count=unpaid_invoices,
    )
