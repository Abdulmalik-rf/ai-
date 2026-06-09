"""Cases: CRUD + on-demand AI analysis."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenancy import TenantQuery
from app.models import Case
from app.schemas.case import CaseAnalysisResponse, CaseCreate, CaseRead, CaseUpdate
from app.services.case_analyzer import analyze_case
from app.services.llm import AgentLLMError

router = APIRouter()


@router.get("", response_model=list[CaseRead])
def list_cases(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
    client_id: UUID | None = Query(default=None),
) -> list[CaseRead]:
    if client_id is None:
        rows = TenantQuery.list_(
            db, Case, principal.tenant_id, limit=limit, offset=offset
        )
    else:
        stmt = (
            select(Case)
            .where(Case.tenant_id == principal.tenant_id)
            .where(Case.client_id == client_id)
            .order_by(Case.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list(db.execute(stmt).scalars())
    return [CaseRead.model_validate(r) for r in rows]


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
def create_case(
    body: CaseCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseRead:
    case = Case(
        tenant_id=principal.tenant_id,
        reference=body.reference,
        title=body.title,
        description=body.description,
        domain=body.domain,
        client_id=body.client_id,
        assigned_lawyer_id=body.assigned_lawyer_id,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return CaseRead.model_validate(case)


@router.get("/{case_id}", response_model=CaseRead)
def get_case(
    case_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseRead:
    case = TenantQuery.get(db, Case, principal.tenant_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return CaseRead.model_validate(case)


@router.patch("/{case_id}", response_model=CaseRead)
def update_case(
    case_id: UUID,
    body: CaseUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseRead:
    case = TenantQuery.get(db, Case, principal.tenant_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(case, field, value)

    db.add(case)
    db.commit()
    db.refresh(case)
    return CaseRead.model_validate(case)


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_case(
    case_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    case = TenantQuery.get(db, Case, principal.tenant_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    db.delete(case)
    db.commit()


class AnalyzeRequest(BaseModel):
    locale: str = Field(default="ar", pattern=r"^(ar|en)$")


@router.post("/{case_id}/analyze", response_model=CaseAnalysisResponse)
def analyze(
    case_id: UUID,
    body: AnalyzeRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> CaseAnalysisResponse:
    case = TenantQuery.get(db, Case, principal.tenant_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    try:
        return analyze_case(db, case=case, locale=body.locale)
    except AgentLLMError as exc:
        # Surface AI-provider auth failure as a clear 502 so the dashboard
        # shows "AI is temporarily unavailable" rather than a generic 500.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "AI provider authentication failed. Refresh the configured "
                "LLM credentials (ChatGPT OAuth token / Gemini OAuth)."
            ),
        ) from exc
