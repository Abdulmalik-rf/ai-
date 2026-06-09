"""Pydantic schemas for the multi-advisor memo review + Najiz final review.

Wire types only — see `services/memo_review/*.py` for orchestration logic.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Memo review (multi-advisor)
# ---------------------------------------------------------------------------


class MemoReviewCreate(BaseModel):
    case_id: UUID | None = None
    case_title: str = Field(..., min_length=1, max_length=500)
    case_type: str | None = Field(None, max_length=120)
    facts: str | None = None
    claims: str | None = None
    memo_text: str = Field(..., min_length=20)
    notes: str | None = None
    mode: Literal["standard", "deep", "custom"] = "deep"
    selected_advisors: list[str] | None = None
    want_revised_memo: bool = True
    attached_document_ids: list[UUID] | None = None


class AdvisorReport(BaseModel):
    """One advisor's structured output (spec §7 fixed template)."""

    advisor_id: str
    status: Literal["queued", "running", "done", "failed"]
    assessment: Literal["strong", "medium", "weak"] | None = None
    impact_level: Literal["high", "medium", "low"] | None = None
    observations: list[str] = Field(default_factory=list)
    risk_points: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    extra: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MemoReviewFinalSummary(BaseModel):
    """Output of the Final Review Manager (spec §6)."""

    general_assessment: dict[str, str]
    """{ case_strength, memo_strength, risk_level, memo_readiness } each in {strong,medium,weak} or {low,medium,high}."""

    top_priorities: list[str] = Field(..., min_length=1, max_length=5)
    """Top 5 modification priorities (spec §8 Second)."""

    summary_of_observations: list[str] = Field(default_factory=list)
    """De-duplicated cross-advisor observations."""

    remaining_risks: list[str] = Field(default_factory=list)
    final_recommendation: str
    final_alerts: list[str] = Field(default_factory=list)
    human_review_points: list[str] = Field(default_factory=list)


class MemoReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID | None
    created_by: UUID | None
    case_title: str
    case_type: str | None
    facts: str | None
    claims: str | None
    memo_text: str
    notes: str | None
    mode: str
    selected_advisors: list[str] | None
    want_revised_memo: bool
    status: str
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    final_summary: dict[str, Any] | None
    revised_memo: str | None
    attached_document_ids: list[UUID] | None
    created_at: datetime
    updated_at: datetime
    advisors: list[AdvisorReport] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Final review (Najiz gate)
# ---------------------------------------------------------------------------


FinalCheckId = Literal[
    "basis",
    "statutes",
    "facts_names_dates",
    "requests",
    "procedures",
    "contradictions",
    "hallucination",
    "submission_readiness",
]


class FinalReviewCheckResult(BaseModel):
    """One of the 8 mandatory checks (spec Note 2 §"What does the final review examine")."""

    check_id: FinalCheckId
    status: Literal["pass", "warn", "fail"]
    """ pass = no issue ; warn = needs attention ; fail = blocker """
    summary: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    """Each finding: { severity, message, location?, quote?, suggested_fix? }."""


class FinalReviewCreate(BaseModel):
    case_id: UUID | None = None
    memo_review_id: UUID | None = None
    memo_text: str = Field(..., min_length=20)
    context: dict[str, Any] | None = None
    """ Optional anchor data: { parties, claims, dates, amounts, contracts }. """
    attached_document_ids: list[UUID] | None = None


class FinalReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: UUID | None
    memo_review_id: UUID | None
    created_by: UUID | None
    memo_text: str
    context: dict[str, Any] | None
    attached_document_ids: list[UUID] | None
    status: str
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    verdict: str | None
    risk_level: str | None
    checks: dict[str, Any] | None
    critical_errors: list[dict[str, Any]] | None
    required_modifications: list[str] | None
    human_review_points: list[str] | None
    created_at: datetime
    updated_at: datetime
