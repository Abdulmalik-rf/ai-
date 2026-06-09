"""Consultation (Legal Opinion Engine) routes.

    POST   /v1/consultations        start a consultation (async background run)
    GET    /v1/consultations        list tenant consultations
    GET    /v1/consultations/{id}   status + advisors + final opinion
    DELETE /v1/consultations/{id}   delete
    GET    /v1/consultations/advisors  advisor catalogue
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenancy import TenantQuery
from app.models.consultation import Consultation, ConsultationAdvisor
from app.schemas.consultation import (
    AdvisorOpinion,
    ConsultationCreate,
    ConsultationRead,
)
from app.services.consultation import (
    ADVISORS,
    DEEP_MODE_ADVISORS,
    STANDARD_MODE_ADVISORS,
    run_consultation,
    start_consultation,
)

router = APIRouter()


def _to_opinion(row: ConsultationAdvisor) -> AdvisorOpinion:
    return AdvisorOpinion(
        advisor_id=row.advisor_id,
        status=row.status if isinstance(row.status, str) else row.status.value,
        position=row.position,
        confidence=row.confidence,
        key_points=row.key_points or [],
        citations=row.citations or [],
        caveats=row.caveats or [],
        extra=row.extra,
        error=row.error,
    )


def _hydrate(db: Session, c: Consultation) -> ConsultationRead:
    advisors = db.execute(
        select(ConsultationAdvisor)
        .where(ConsultationAdvisor.consultation_id == c.id)
        .order_by(ConsultationAdvisor.created_at)
    ).scalars().all()
    read = ConsultationRead.model_validate(c)
    read.advisors = [_to_opinion(a) for a in advisors]
    return read


@router.get("/advisors")
def list_advisors() -> dict:
    return {
        "advisors": [
            {"id": a.id, "name_en": a.name_en, "name_ar": a.name_ar}
            for a in ADVISORS.values()
        ],
        "modes": {
            "standard": list(STANDARD_MODE_ADVISORS),
            "deep": list(DEEP_MODE_ADVISORS),
        },
    }


@router.post("", response_model=ConsultationRead, status_code=status.HTTP_202_ACCEPTED)
def create_consultation(
    body: ConsultationCreate,
    bg: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> ConsultationRead:
    c = start_consultation(db, tenant_id=principal.tenant_id, user_id=principal.user_id, payload=body)
    bg.add_task(run_consultation, c.id)
    return _hydrate(db, c)


@router.get("", response_model=list[ConsultationRead])
def list_consultations(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    client_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[ConsultationRead]:
    q = TenantQuery.filter(select(Consultation), Consultation, principal.tenant_id).order_by(
        Consultation.created_at.desc()
    )
    if client_id is not None:
        q = q.where(Consultation.client_id == client_id)
    rows = db.execute(q.limit(limit)).scalars().all()
    return [_hydrate(db, r) for r in rows]


@router.get("/{consultation_id}", response_model=ConsultationRead)
def get_consultation(
    consultation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> ConsultationRead:
    c = TenantQuery.get(db, Consultation, principal.tenant_id, consultation_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Consultation not found.")
    return _hydrate(db, c)


@router.delete("/{consultation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_consultation(
    consultation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    c = TenantQuery.get(db, Consultation, principal.tenant_id, consultation_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Consultation not found.")
    db.delete(c)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
