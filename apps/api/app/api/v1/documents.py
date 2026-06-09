"""Documents: upload, list, get, delete, presigned download.

Upload kicks off an async ingestion task (Celery) that parses, chunks, and
embeds the file. The endpoint returns a 202 immediately.
"""
from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenancy import TenantQuery
from app.models import Document, DocumentSource, DocumentStatus
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.services import storage
from app.services.billing import LimitExceeded, assert_within_limits, record_usage
from app.workers.tasks import ingest_document_task

router = APIRouter()

ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}
MAX_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload(
    file: Annotated[UploadFile, File(...)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    case_id: Annotated[UUID | None, Form()] = None,
    language: Annotated[str, Form()] = "ar",
) -> DocumentUploadResponse:
    try:
        assert_within_limits(db, tenant_id=principal.tenant_id, kind="document_upload")
    except LimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Plan limit reached: {exc.kind} ({exc.limit}).",
        ) from exc

    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported MIME type: {file.content_type}",
        )

    body = await file.read()
    if len(body) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(body) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large.")

    doc_id = uuid.uuid4()
    key = storage.storage_key_for(principal.tenant_id, doc_id, file.filename or "file.bin")

    from io import BytesIO

    storage.upload_fileobj(key, BytesIO(body), file.content_type)

    doc = Document(
        id=doc_id,
        tenant_id=principal.tenant_id,
        title=file.filename or "Untitled",
        source=DocumentSource.UPLOAD,
        status=DocumentStatus.UPLOADED,
        storage_key=key,
        mime_type=file.content_type,
        byte_size=len(body),
        page_count=0,
        language=language,
        case_id=case_id,
        extra_metadata={"original_filename": file.filename},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    record_usage(db, tenant_id=principal.tenant_id, kind="document_upload")

    task = ingest_document_task.delay(str(principal.tenant_id), str(doc.id))

    return DocumentUploadResponse(
        document=DocumentRead.model_validate(doc),
        upload_id=task.id,
    )


@router.get("", response_model=list[DocumentRead])
def list_documents(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[DocumentRead]:
    rows = TenantQuery.list_(db, Document, principal.tenant_id, limit=limit, offset=offset)
    return [DocumentRead.model_validate(r) for r in rows]


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> DocumentRead:
    doc = TenantQuery.get(db, Document, principal.tenant_id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentRead.model_validate(doc)


@router.get("/{document_id}/download-url")
def download_url(
    document_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    doc = TenantQuery.get(db, Document, principal.tenant_id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"url": storage.presigned_download_url(doc.storage_key)}


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_document(
    document_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    doc = TenantQuery.get(db, Document, principal.tenant_id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(doc)
    db.commit()
