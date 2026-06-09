"""Celery tasks.

Each task opens its own DB session because Celery workers don't share state
with the FastAPI request lifecycle.
"""
from __future__ import annotations

from uuid import UUID

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models import Case, Document, DocumentStatus
from app.services.case_analyzer import analyze_case
from app.services.contract_analyzer import review_contract
from app.services.document_processor import parse
from app.services.legal_chunker import chunk_legal_pages, detect_language
from app.services.rag import index_document_chunks
from app.services.storage import download_to_memory
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.ingest_document_task", bind=True, max_retries=3)
def ingest_document_task(self, tenant_id: str, document_id: str) -> dict:
    """Parse → chunk → embed → index a single uploaded document."""
    log.info("ingest_start", document_id=document_id)
    db = SessionLocal()
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            return {"error": "document_not_found"}

        doc.status = DocumentStatus.PROCESSING
        db.add(doc)
        db.commit()

        try:
            raw = download_to_memory(doc.storage_key)
            pages = parse(raw, doc.mime_type)
            doc.page_count = len(pages)

            language = doc.language or detect_language(pages)
            parsed = chunk_legal_pages(pages, language=language)
            n = index_document_chunks(
                db,
                tenant_id=UUID(tenant_id),
                document_id=doc.id,
                chunks=parsed,
                legal_domain=doc.legal_domain,
            )

            doc.status = DocumentStatus.INDEXED
            db.add(doc)
            db.commit()
            log.info("ingest_done", document_id=document_id, chunks=n)
            return {"chunks": n, "pages": len(pages)}
        except Exception as exc:  # noqa: BLE001
            log.exception("ingest_failed", document_id=document_id)
            doc.status = DocumentStatus.FAILED
            db.add(doc)
            db.commit()
            raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.contract_review_task")
def contract_review_task(tenant_id: str, document_id: str, locale: str = "ar") -> dict:
    db = SessionLocal()
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None or str(doc.tenant_id) != tenant_id:
            return {"error": "document_not_found"}
        result = review_contract(db, document=doc, locale=locale)
        return result.model_dump(mode="json")
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.case_analysis_task")
def case_analysis_task(tenant_id: str, case_id: str, locale: str = "ar") -> dict:
    db = SessionLocal()
    try:
        case = db.get(Case, UUID(case_id))
        if case is None or str(case.tenant_id) != tenant_id:
            return {"error": "case_not_found"}
        result = analyze_case(db, case=case, locale=locale)
        return result.model_dump(mode="json")
    finally:
        db.close()
