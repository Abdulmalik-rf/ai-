"""Pydantic schemas for the Legal Opinion Engine (consultations)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConsultationCreate(BaseModel):
    client_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=500)
    question: str = Field(..., min_length=10)
    situation: str | None = None
    client_type: Literal["individual", "company", "government", "other"] | None = None
    domain: str | None = None
    mode: Literal["standard", "deep"] = "standard"
    attached_document_ids: list[UUID] | None = None


class AdvisorOpinion(BaseModel):
    advisor_id: str
    status: Literal["queued", "running", "done", "failed"]
    position: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    key_points: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    extra: dict[str, Any] | None = None
    error: str | None = None


class ConsultationOpinion(BaseModel):
    """The synthesized client-ready legal opinion."""

    executive_answer: str
    """Clear answer: yes / no / it-depends + one paragraph."""
    answer_disposition: Literal["yes", "no", "depends", "conditional"] | None = None
    legal_basis: list[dict[str, Any]] = Field(default_factory=list)
    """[ {statute, article, summary} ] — the grounding."""
    analysis: str | None = None
    options: list[dict[str, Any]] = Field(default_factory=list)
    """[ {option, pros[], cons[], rank} ] — ranked lawful paths."""
    risks: list[str] = Field(default_factory=list)
    recommended_action: str | None = None
    caveats: list[str] = Field(default_factory=list)
    human_review_points: list[str] = Field(default_factory=list)


class ConsultationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID | None
    created_by: UUID | None
    title: str
    question: str
    situation: str | None
    client_type: str | None
    domain: str | None
    mode: str
    attached_document_ids: list[UUID] | None
    status: str
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    framing: dict[str, Any] | None
    grounding: dict[str, Any] | None
    final_opinion: dict[str, Any] | None
    verification: dict[str, Any] | None
    confidence_level: str | None
    needs_human_review: bool
    created_at: datetime
    updated_at: datetime
    advisors: list[AdvisorOpinion] = Field(default_factory=list)
