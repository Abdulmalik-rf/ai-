from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ContractFinding(BaseModel):
    severity: Literal["info", "low", "medium", "high", "critical"]
    category: str
    title: str
    description: str
    clause_excerpt: str | None = None
    page_number: int | None = None


class ContractSuggestion(BaseModel):
    title: str
    rationale: str
    suggested_clause: str
    targets_finding: int | None = None  # index into findings list


class ContractAdvisorOpinion(BaseModel):
    """One advisor's independent read of the contract (multi-advisor panel)."""

    advisor_id: str
    name: str
    assessment: str = ""
    favors: Literal["client", "counterparty", "balanced", "na"] = "na"
    findings: list[ContractFinding] = Field(default_factory=list)


class ContractReviewResponse(BaseModel):
    document_id: UUID
    summary: str
    findings: list[ContractFinding]
    suggestions: list[ContractSuggestion]
    missing_clauses: list[str] = Field(default_factory=list)
    risk_score: int = Field(ge=0, le=100)
    locale: str
    # Multi-advisor panel additions (default-empty → backward compatible).
    advisors: list[ContractAdvisorOpinion] = Field(default_factory=list)
    party_favorability: str | None = None
