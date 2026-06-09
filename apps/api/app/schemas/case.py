from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.case import CasePriority, CaseStatus, LegalDomain


class CaseCreate(BaseModel):
    reference: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    domain: LegalDomain = LegalDomain.OTHER
    priority: CasePriority = CasePriority.MEDIUM
    client_id: UUID | None = None
    assigned_lawyer_id: UUID | None = None
    opposing_party_name: str | None = None
    opposing_counsel: str | None = None
    court_name: str | None = None
    court_circuit: str | None = None
    court_case_number: str | None = None
    judge_name: str | None = None
    opened_at: date | None = None


class CaseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    domain: LegalDomain | None = None
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    client_id: UUID | None = None
    assigned_lawyer_id: UUID | None = None
    opposing_party_name: str | None = None
    opposing_counsel: str | None = None
    court_name: str | None = None
    court_circuit: str | None = None
    court_case_number: str | None = None
    judge_name: str | None = None
    opened_at: date | None = None
    closed_at: date | None = None


class CaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference: str
    title: str
    description: str | None
    domain: LegalDomain
    status: CaseStatus
    priority: CasePriority
    client_id: UUID | None
    assigned_lawyer_id: UUID | None
    opposing_party_name: str | None
    opposing_counsel: str | None
    court_name: str | None
    court_circuit: str | None
    court_case_number: str | None
    judge_name: str | None
    opened_at: date | None
    closed_at: date | None
    next_hearing_at: datetime | None
    ai_analysis: dict
    created_at: datetime
    updated_at: datetime


class CaseAnalysisResponse(BaseModel):
    case_id: UUID
    summary: str
    legal_issues: list[str]
    suggested_strategy: list[str]
    relevant_laws: list[str]
    risk_assessment: str
    locale: str
