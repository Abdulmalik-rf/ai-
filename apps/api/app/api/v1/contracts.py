"""Contract review: synchronous endpoint for now (small contracts) and an
async variant via Celery for large ones.

The latest review per document is persisted onto `documents.extra_metadata`
so the dashboard can re-render it after the user navigates away — they
don't have to re-burn AI credits or wait again just because they clicked
into another section.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenancy import TenantQuery
from app.models import Document
from app.models.contract_review_job import ContractReviewJob
from app.schemas.contract import ContractReviewResponse
from app.services.billing import LimitExceeded, assert_within_limits, record_usage
from app.services.contract_analyzer import review_contract
from app.services.contract_review_runner import run_job, start_job
from app.workers.tasks import contract_review_task

router = APIRouter()


def _job_payload(job: ContractReviewJob) -> dict:
    return {
        "job_id": str(job.id),
        "document_id": str(job.document_id),
        "status": job.status if isinstance(job.status, str) else job.status.value,
        "mode": job.mode,
        "advisors": job.advisors or [],
        "result": job.result,
        "error": job.error,
    }


class ContractReviewRequest(BaseModel):
    document_id: UUID
    locale: str = Field(default="ar", pattern=r"^(ar|en)$")
    async_mode: bool = False
    mode: str = Field(default="standard", pattern=r"^(standard|deep)$")


def _persist_review(db: Session, *, doc: Document, result: ContractReviewResponse) -> None:
    """Stash the result onto the document so the user sees it next visit.

    We deep-copy `extra_metadata` before mutating because SQLAlchemy's
    JSONB change tracking doesn't pick up in-place edits — assigning the
    attribute is what triggers the UPDATE.
    """
    meta = copy.deepcopy(doc.extra_metadata or {})
    meta["last_contract_review"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "result": result.model_dump(mode="json"),
    }
    doc.extra_metadata = meta
    db.add(doc)
    db.commit()


@router.post("/review", response_model=ContractReviewResponse | dict)
def review(
    body: ContractReviewRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    try:
        assert_within_limits(db, tenant_id=principal.tenant_id, kind="contract_review")
    except LimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Plan limit reached: {exc.kind} ({exc.limit}).",
        ) from exc

    doc = TenantQuery.get(db, Document, principal.tenant_id, body.document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    if body.async_mode:
        task = contract_review_task.delay(str(principal.tenant_id), str(doc.id), body.locale)
        return {"task_id": task.id}

    result = review_contract(db, document=doc, locale=body.locale, mode=body.mode)
    record_usage(db, tenant_id=principal.tenant_id, kind="contract_review")
    _persist_review(db, doc=doc, result=result)
    return result


# --- Async multi-advisor review with progress ------------------------------


@router.post("/review-jobs", status_code=status.HTTP_202_ACCEPTED)
def start_review_job(
    body: ContractReviewRequest,
    bg: BackgroundTasks,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Kick off a multi-advisor contract review as a background job.

    Returns the queued job (with the advisor list) immediately; the client
    polls GET /review-jobs/{job_id} and watches advisors finish one by one.
    """
    try:
        assert_within_limits(db, tenant_id=principal.tenant_id, kind="contract_review")
    except LimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Plan limit reached: {exc.kind} ({exc.limit}).",
        ) from exc

    doc = TenantQuery.get(db, Document, principal.tenant_id, body.document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    job = start_job(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        document_id=doc.id,
        locale=body.locale,
        mode=body.mode,
    )
    record_usage(db, tenant_id=principal.tenant_id, kind="contract_review")
    bg.add_task(run_job, job.id)
    return _job_payload(job)


@router.get("/review-jobs/{job_id}")
def get_review_job(
    job_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    job = TenantQuery.get(db, ContractReviewJob, principal.tenant_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Review job not found.")
    return _job_payload(job)


@router.get(
    "/review/{document_id}",
    response_model=ContractReviewResponse | None,
)
def get_last_review(
    document_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ContractReviewResponse | None:
    """Return the most recent persisted review for a document, or null."""
    doc = TenantQuery.get(db, Document, principal.tenant_id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    meta = doc.extra_metadata or {}
    stash = meta.get("last_contract_review")
    if not isinstance(stash, dict):
        return None
    payload = stash.get("result")
    if not isinstance(payload, dict):
        return None
    return ContractReviewResponse.model_validate(payload)
