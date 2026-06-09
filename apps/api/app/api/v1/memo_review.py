"""Memo review + Najiz final-review routes.

Endpoints
---------
    POST   /v1/memo-reviews           start a multi-advisor review (async)
    GET    /v1/memo-reviews           list reviews for the tenant
    GET    /v1/memo-reviews/{id}      review status + advisor reports + final
    DELETE /v1/memo-reviews/{id}      delete a review
    GET    /v1/memo-reviews/advisors  list available advisors (Phase-1 only today)

    POST   /v1/final-reviews          start a Najiz pre-submission gate
    GET    /v1/final-reviews          list final reviews for the tenant
    GET    /v1/final-reviews/{id}     final review status + verdict + findings
    DELETE /v1/final-reviews/{id}     delete a final review

The work runs in a FastAPI BackgroundTask so the POST returns immediately
with a queued row + identifier — the client polls the GET endpoint until
status moves to `done`. (We can swap to Celery later with no API changes —
the work is already split across short, idempotent stages.)
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
from app.models.memo_review import (
    FinalReview,
    FinalReviewStatus,
    MemoReview,
    MemoReviewAdvisor,
    ReviewStatus,
)
from app.schemas.memo_review import (
    AdvisorReport,
    FinalReviewCreate,
    FinalReviewRead,
    MemoReviewCreate,
    MemoReviewRead,
)
from app.services.memo_review import (
    ADVISORS,
    DEEP_MODE_ADVISORS,
    PHASE_1_ADVISORS,
    PHASE_2_ADVISORS,
    PHASE_3_ADVISORS,
    STANDARD_MODE_ADVISORS,
    run_final_review,
    run_memo_review,
    start_final_review,
    start_memo_review,
)


# ---------------------------------------------------------------------------
# Memo reviews
# ---------------------------------------------------------------------------

memo_reviews_router = APIRouter()


def _to_advisor_report(row: MemoReviewAdvisor) -> AdvisorReport:
    return AdvisorReport(
        advisor_id=row.advisor_id,
        status=row.status if isinstance(row.status, str) else row.status.value,
        assessment=row.assessment,
        impact_level=row.impact_level,
        observations=row.observations or [],
        risk_points=row.risk_points or [],
        recommendations=row.recommendations or [],
        extra=row.extra,
        error=row.error,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _hydrate(db: Session, review: MemoReview) -> MemoReviewRead:
    advisors = (
        db.execute(
            select(MemoReviewAdvisor)
            .where(MemoReviewAdvisor.review_id == review.id)
            .order_by(MemoReviewAdvisor.created_at)
        )
        .scalars()
        .all()
    )
    read = MemoReviewRead.model_validate(review)
    read.advisors = [_to_advisor_report(a) for a in advisors]
    return read


@memo_reviews_router.get("/advisors")
def list_advisors() -> dict:
    """Catalog of advisors + which phase each belongs to."""
    return {
        "advisors": [
            {
                "id": a.id,
                "name_en": a.name_en,
                "name_ar": a.name_ar,
                "main_question_en": a.main_question_en,
                "main_question_ar": a.main_question_ar,
                "available": not a.system_prompt.startswith("_PHASE_"),
            }
            for a in ADVISORS.values()
        ],
        "phases": {
            "phase_1": list(PHASE_1_ADVISORS),
            "phase_2": list(PHASE_2_ADVISORS),
            "phase_3": list(PHASE_3_ADVISORS),
        },
        "modes": {
            "standard": list(STANDARD_MODE_ADVISORS),
            "deep": list(DEEP_MODE_ADVISORS),
        },
    }


@memo_reviews_router.post(
    "",
    response_model=MemoReviewRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_memo_review(
    body: MemoReviewCreate,
    bg: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> MemoReviewRead:
    try:
        review = start_memo_review(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            payload=body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Fan out the actual review work to a background task — the client polls
    # GET /v1/memo-reviews/{id} until status="done".
    bg.add_task(run_memo_review, review.id)
    return _hydrate(db, review)


@memo_reviews_router.get("", response_model=list[MemoReviewRead])
def list_memo_reviews(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    case_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[MemoReviewRead]:
    q = TenantQuery.filter(select(MemoReview), MemoReview, principal.tenant_id).order_by(
        MemoReview.created_at.desc()
    )
    if case_id is not None:
        q = q.where(MemoReview.case_id == case_id)
    rows = db.execute(q.limit(limit)).scalars().all()
    return [_hydrate(db, r) for r in rows]


@memo_reviews_router.get("/{review_id}", response_model=MemoReviewRead)
def get_memo_review(
    review_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> MemoReviewRead:
    review = TenantQuery.get(db, MemoReview, principal.tenant_id, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Memo review not found.")
    return _hydrate(db, review)


@memo_reviews_router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memo_review(
    review_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    review = TenantQuery.get(db, MemoReview, principal.tenant_id, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Memo review not found.")
    db.delete(review)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Final reviews (Najiz gate)
# ---------------------------------------------------------------------------

final_reviews_router = APIRouter()


@final_reviews_router.post(
    "",
    response_model=FinalReviewRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_final_review(
    body: FinalReviewCreate,
    bg: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> FinalReviewRead:
    fr = start_final_review(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        payload=body,
    )
    bg.add_task(run_final_review, fr.id)
    return FinalReviewRead.model_validate(fr)


@final_reviews_router.get("", response_model=list[FinalReviewRead])
def list_final_reviews(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    case_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[FinalReviewRead]:
    q = TenantQuery.filter(select(FinalReview), FinalReview, principal.tenant_id).order_by(
        FinalReview.created_at.desc()
    )
    if case_id is not None:
        q = q.where(FinalReview.case_id == case_id)
    rows = db.execute(q.limit(limit)).scalars().all()
    return [FinalReviewRead.model_validate(r) for r in rows]


@final_reviews_router.get("/{review_id}", response_model=FinalReviewRead)
def get_final_review(
    review_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> FinalReviewRead:
    fr = TenantQuery.get(db, FinalReview, principal.tenant_id, review_id)
    if fr is None:
        raise HTTPException(status_code=404, detail="Final review not found.")
    return FinalReviewRead.model_validate(fr)


@final_reviews_router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_final_review(
    review_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Response:
    fr = TenantQuery.get(db, FinalReview, principal.tenant_id, review_id)
    if fr is None:
        raise HTTPException(status_code=404, detail="Final review not found.")
    db.delete(fr)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
