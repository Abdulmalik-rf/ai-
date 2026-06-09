"""Pydantic schemas for the CRM workspace: tasks, hearings, time entries,
case notes, contacts, activities, and the dashboard summary.

Kept in one file because every entity has the same Create/Update/Read trio
and groupings them surfaces structural symmetry rather than scatter."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.activity import ActivityKind
from app.models.contact import ContactKind
from app.models.hearing import HearingKind, HearingStatus
from app.models.task import TaskPriority, TaskStatus
from app.models.time_entry import TimeActivityKind


# =============================================================================
# Tasks
# =============================================================================


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    case_id: UUID | None = None
    client_id: UUID | None = None
    assignee_id: UUID | None = None
    due_date: date | None = None
    reminder_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    case_id: UUID | None = None
    client_id: UUID | None = None
    assignee_id: UUID | None = None
    due_date: date | None = None
    reminder_at: datetime | None = None
    completed_at: datetime | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    case_id: UUID | None
    client_id: UUID | None
    assignee_id: UUID | None
    creator_id: UUID | None
    due_date: date | None
    reminder_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Hearings
# =============================================================================


class HearingCreate(BaseModel):
    case_id: UUID
    scheduled_at: datetime
    kind: HearingKind = HearingKind.HEARING
    duration_minutes: int | None = None
    court_name: str | None = None
    court_circuit: str | None = None
    court_room: str | None = None
    judge_name: str | None = None
    opposing_counsel: str | None = None
    assigned_lawyer_id: UUID | None = None
    notes: str | None = None


class HearingUpdate(BaseModel):
    scheduled_at: datetime | None = None
    kind: HearingKind | None = None
    status: HearingStatus | None = None
    duration_minutes: int | None = None
    court_name: str | None = None
    court_circuit: str | None = None
    court_room: str | None = None
    judge_name: str | None = None
    opposing_counsel: str | None = None
    assigned_lawyer_id: UUID | None = None
    outcome: str | None = None
    notes: str | None = None


class HearingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    scheduled_at: datetime
    kind: HearingKind
    status: HearingStatus
    duration_minutes: int | None
    court_name: str | None
    court_circuit: str | None
    court_room: str | None
    judge_name: str | None
    opposing_counsel: str | None
    assigned_lawyer_id: UUID | None
    outcome: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Time entries
# =============================================================================


class TimeEntryCreate(BaseModel):
    case_id: UUID | None = None
    activity_kind: TimeActivityKind = TimeActivityKind.OTHER
    work_date: date
    minutes: int = Field(ge=1, le=24 * 60)
    description: str | None = None
    billable: bool = True
    billing_rate_per_hour: Decimal | None = None


class TimeEntryUpdate(BaseModel):
    case_id: UUID | None = None
    activity_kind: TimeActivityKind | None = None
    work_date: date | None = None
    minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    description: str | None = None
    billable: bool | None = None
    billing_rate_per_hour: Decimal | None = None


class TimeEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID | None
    user_id: UUID
    activity_kind: TimeActivityKind
    work_date: date
    minutes: int
    description: str | None
    billable: bool
    billing_rate_per_hour: Decimal | None
    invoice_id: UUID | None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Case notes
# =============================================================================


class CaseNoteCreate(BaseModel):
    case_id: UUID
    body: str = Field(min_length=1)
    is_internal: bool = True


class CaseNoteUpdate(BaseModel):
    body: str | None = None
    is_internal: bool | None = None


class CaseNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID
    author_id: UUID | None
    body: str
    is_internal: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Contacts (non-client people in the firm's orbit)
# =============================================================================


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: ContactKind = ContactKind.OTHER
    organization: str | None = None
    title: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class ContactUpdate(BaseModel):
    name: str | None = None
    kind: ContactKind | None = None
    organization: str | None = None
    title: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: ContactKind
    organization: str | None
    title: str | None
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Activities (append-only event log)
# =============================================================================


class ActivityCreate(BaseModel):
    case_id: UUID | None = None
    client_id: UUID | None = None
    kind: ActivityKind = ActivityKind.OTHER
    summary: str = Field(min_length=1, max_length=500)
    body: str | None = None
    extra: dict = Field(default_factory=dict)
    occurred_at: datetime | None = None


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID | None
    client_id: UUID | None
    user_id: UUID | None
    kind: ActivityKind
    summary: str
    body: str | None
    extra: dict
    occurred_at: datetime
    created_at: datetime


# =============================================================================
# Dashboard summary
# =============================================================================


class CaseSummary(BaseModel):
    id: UUID
    reference: str
    title: str
    status: str
    next_hearing_at: datetime | None


class TaskSummary(BaseModel):
    id: UUID
    title: str
    priority: TaskPriority
    due_date: date | None
    case_id: UUID | None


class HearingSummary(BaseModel):
    id: UUID
    case_id: UUID
    case_title: str | None
    scheduled_at: datetime
    court_name: str | None
    kind: HearingKind


class ActivitySummary(BaseModel):
    id: UUID
    kind: ActivityKind
    summary: str
    occurred_at: datetime
    case_id: UUID | None
    client_id: UUID | None


class DashboardSummary(BaseModel):
    """One-shot payload powering the dashboard home page."""

    # Counts
    total_clients: int
    active_clients: int
    leads: int
    open_cases: int
    cases_in_court: int
    overdue_tasks: int
    open_tasks: int

    # Upcoming
    today_hearings: list[HearingSummary]
    upcoming_hearings: list[HearingSummary]
    my_tasks: list[TaskSummary]
    recent_activities: list[ActivitySummary]

    # Cash flow
    unbilled_minutes_30d: int
    unpaid_invoices_count: int
