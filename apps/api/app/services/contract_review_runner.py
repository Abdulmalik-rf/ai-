"""Async contract-review job runner with per-advisor progress.

Mirrors the consultation/memo pattern: a job row tracks each advisor's
status in a JSONB array so the UI can poll and watch advisors finish one by
one. The final synthesized review is stored on the job AND mirrored onto the
document (backward compat with the old sync `last_contract_review`).
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import Document
from app.models.contract_review_job import ContractReviewJob, ContractReviewJobStatus
from app.services.contract_advisors import advisor_label, panel_advisor_ids, run_panel
from app.services.contract_analyzer import _coerce_findings  # reuse coercion
from app.schemas.contract import (
    ContractAdvisorOpinion,
    ContractReviewResponse,
    ContractSuggestion,
)
from app.services.document_processor import parse
from app.services.storage import download_to_memory

log = get_logger(__name__)


def start_job(db: Session, *, tenant_id: UUID, user_id: UUID | None, document_id: UUID, locale: str, mode: str) -> ContractReviewJob:
    advisor_ids = panel_advisor_ids(mode)
    job = ContractReviewJob(
        id=uuid4(),
        tenant_id=tenant_id,
        document_id=document_id,
        created_by=user_id,
        status=ContractReviewJobStatus.QUEUED,
        mode=mode,
        locale=locale,
        advisors=[
            {"advisor_id": aid, "name": advisor_label(aid, locale), "status": "queued",
             "favors": "na", "findings_count": 0}
            for aid in advisor_ids
        ],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _update_advisor(job_id: UUID, advisor_id: str, **fields) -> None:
    """Update one advisor's progress entry, serialized via a row lock."""
    with SessionLocal() as db:
        job = db.execute(
            select(ContractReviewJob).where(ContractReviewJob.id == job_id).with_for_update()
        ).scalar_one_or_none()
        if job is None:
            return
        advisors = copy.deepcopy(job.advisors or [])
        for a in advisors:
            if a.get("advisor_id") == advisor_id:
                a.update(fields)
                break
        job.advisors = advisors
        db.commit()


def _persist_to_document(db: Session, document_id: UUID, result: ContractReviewResponse) -> None:
    doc = db.get(Document, document_id)
    if doc is None:
        return
    meta = copy.deepcopy(doc.extra_metadata or {})
    meta["last_contract_review"] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "result": result.model_dump(mode="json"),
    }
    doc.extra_metadata = meta
    db.add(doc)
    db.commit()


def run_job(job_id: UUID) -> None:
    # Load job + extract contract text.
    with SessionLocal() as db:
        job = db.get(ContractReviewJob, job_id)
        if job is None or job.status not in (ContractReviewJobStatus.QUEUED, ContractReviewJobStatus.FAILED):
            return
        job.status = ContractReviewJobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.error = None
        db.commit()
        document_id = job.document_id
        locale = job.locale
        mode = job.mode
        doc = db.get(Document, document_id)
        if doc is None:
            job.status = ContractReviewJobStatus.FAILED
            job.error = "Document not found."
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        storage_key = doc.storage_key
        mime = doc.mime_type

    try:
        raw = download_to_memory(storage_key)
        pages = parse(raw, mime)
        full_text = "\n\n".join(f"--- Page {p} ---\n{txt}" for p, txt in pages if txt.strip())[:80_000]

        # Mark all advisors "running" at start (they fan out in parallel).
        for aid in panel_advisor_ids(mode):
            _update_advisor(job_id, aid, status="running")

        def _on_done(aid: str, result: dict) -> None:
            _update_advisor(
                job_id, aid,
                status="done",
                favors=result.get("favors", "na"),
                findings_count=len(result.get("findings", []) or []),
            )

        def _on_synth() -> None:
            with SessionLocal() as db:
                job = db.get(ContractReviewJob, job_id)
                if job:
                    advisors = copy.deepcopy(job.advisors or [])
                    advisors.append({"advisor_id": "_synthesis", "name": "Synthesizing",
                                     "status": "running", "favors": "na", "findings_count": 0})
                    job.advisors = advisors
                    db.commit()

        advisor_opinions, synthesis = run_panel(
            full_text, locale=locale, mode=mode,
            on_advisor_done=_on_done, on_synthesis_start=_on_synth,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("contract_review_job_failed", job_id=str(job_id))
        with SessionLocal() as db:
            job = db.get(ContractReviewJob, job_id)
            if job:
                job.status = ContractReviewJobStatus.FAILED
                job.error = f"{type(exc).__name__}: {exc}"[:2000]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        return

    # Build the typed response.
    advisors = [
        ContractAdvisorOpinion(
            advisor_id=a["advisor_id"], name=a["name"],
            assessment=a.get("assessment", ""),
            favors=a.get("favors") if a.get("favors") in ("client", "counterparty", "balanced", "na") else "na",
            findings=_coerce_findings(a.get("findings")),
        )
        for a in advisor_opinions
    ]
    suggestions: list[ContractSuggestion] = []
    raw_suggestions = synthesis.get("suggestions")
    for s in raw_suggestions if isinstance(raw_suggestions, list) else []:
        if isinstance(s, dict):
            try:
                suggestions.append(ContractSuggestion(
                    title=str(s.get("title", "")), rationale=str(s.get("rationale", "")),
                    suggested_clause=str(s.get("suggested_clause", "")),
                ))
            except Exception:  # noqa: BLE001
                continue
    result = ContractReviewResponse(
        document_id=document_id,
        summary=synthesis.get("summary", ""),
        findings=_coerce_findings(synthesis.get("findings")),
        suggestions=suggestions,
        missing_clauses=[str(m) for m in (synthesis.get("missing_clauses") or []) if str(m).strip()],
        risk_score=int(synthesis.get("risk_score", 0) or 0),
        locale=locale,
        advisors=advisors,
        party_favorability=synthesis.get("party_favorability"),
    )

    with SessionLocal() as db:
        job = db.get(ContractReviewJob, job_id)
        if job is None:
            return
        job.result = result.model_dump(mode="json")
        job.status = ContractReviewJobStatus.DONE
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        _persist_to_document(db, document_id, result)
        log.info("contract_review_job_done", job_id=str(job_id), risk=result.risk_score)
