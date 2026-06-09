"""Platform-admin endpoints. SUPER_ADMIN role only.

Powers the admin panel: tenant management, global Saudi-law dataset uploads,
usage monitoring, and subscription overrides.
"""
from __future__ import annotations

import uuid
from io import BytesIO
from typing import Annotated

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
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import Principal, require_super_admin
from app.db.session import get_db
from app.models import (
    Document,
    DocumentSource,
    DocumentStatus,
    Plan,
    Subscription,
    Tenant,
    UsageEvent,
    User,
)
from app.schemas.tenant import TenantRead
from app.services import storage
from app.workers.tasks import ingest_document_task

router = APIRouter()


# --- Tenants -----------------------------------------------------------------


@router.get("/tenants", response_model=list[TenantRead])
def list_tenants(
    _: Annotated[Principal, Depends(require_super_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TenantRead]:
    rows = list(db.execute(select(Tenant).order_by(Tenant.created_at.desc())).scalars())
    return [TenantRead.model_validate(t) for t in rows]


@router.post("/tenants/{tenant_id}/suspend", status_code=204, response_class=Response, response_model=None)
def suspend_tenant(
    tenant_id: uuid.UUID,
    _: Annotated[Principal, Depends(require_super_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    tenant.is_active = False
    db.add(tenant)
    db.commit()


@router.post("/tenants/{tenant_id}/activate", status_code=204, response_class=Response, response_model=None)
def activate_tenant(
    tenant_id: uuid.UUID,
    _: Annotated[Principal, Depends(require_super_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    tenant.is_active = True
    db.add(tenant)
    db.commit()


# --- Global datasets ---------------------------------------------------------


@router.post("/datasets", status_code=status.HTTP_202_ACCEPTED)
async def upload_global_dataset(
    file: Annotated[UploadFile, File(...)],
    _: Annotated[Principal, Depends(require_super_admin)],
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str, Form()] = "",
    language: Annotated[str, Form()] = "ar",
) -> dict:
    """Upload a base Saudi-law document (e.g., Companies Law, Labor Law).

    These are owned by the platform tenant and visible to every firm.
    """
    platform = db.execute(
        select(Tenant).where(Tenant.slug == "platform")
    ).scalar_one_or_none()
    if platform is None:
        raise HTTPException(
            status_code=500, detail="Platform tenant not seeded — run seed first."
        )

    body = await file.read()
    doc_id = uuid.uuid4()
    key = storage.storage_key_for(platform.id, doc_id, file.filename or "dataset.pdf")
    storage.upload_fileobj(key, BytesIO(body), file.content_type or "application/pdf")

    doc = Document(
        id=doc_id,
        tenant_id=platform.id,
        title=title or (file.filename or "Untitled"),
        source=DocumentSource.GLOBAL_DATASET,
        status=DocumentStatus.UPLOADED,
        storage_key=key,
        mime_type=file.content_type or "application/pdf",
        byte_size=len(body),
        page_count=0,
        language=language,
        extra_metadata={"uploaded_via": "admin"},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    task = ingest_document_task.delay(str(platform.id), str(doc.id))
    return {"document_id": str(doc.id), "task_id": task.id}


# --- Metrics -----------------------------------------------------------------


class PlatformMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenants: int
    users: int
    active_subscriptions: int
    documents: int
    messages_30d: int
    contract_reviews_30d: int


@router.get("/metrics", response_model=PlatformMetrics)
def metrics(
    _: Annotated[Principal, Depends(require_super_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PlatformMetrics:
    tenants = db.scalar(select(func.count()).select_from(Tenant)) or 0
    users = db.scalar(select(func.count()).select_from(User)) or 0
    active_subs = (
        db.scalar(
            select(func.count()).select_from(Subscription).where(
                Subscription.status.in_(["active", "trialing"])
            )
        )
        or 0
    )
    docs = db.scalar(select(func.count()).select_from(Document)) or 0

    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    messages_30d = (
        db.scalar(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.kind == "message",
                UsageEvent.created_at >= cutoff,
            )
        )
        or 0
    )
    cr_30d = (
        db.scalar(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.kind == "contract_review",
                UsageEvent.created_at >= cutoff,
            )
        )
        or 0
    )

    return PlatformMetrics(
        tenants=tenants,
        users=users,
        active_subscriptions=active_subs,
        documents=docs,
        messages_30d=int(messages_30d),
        contract_reviews_30d=int(cr_30d),
    )
