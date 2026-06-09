"""Document drafting endpoint."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenancy import TenantQuery
from app.models import Template
from app.schemas.document import DraftRequest, DraftResponse
from app.services.drafting import draft_document

router = APIRouter()


@router.post("", response_model=DraftResponse)
def draft(
    body: DraftRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> DraftResponse:
    template: Template | None = None
    if body.template_id:
        template = TenantQuery.get(db, Template, principal.tenant_id, body.template_id)
        if template is None:
            # Try global templates (platform-owned)
            template = db.get(Template, body.template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="Template not found.")

    title, body_text, doc = draft_document(
        db,
        tenant_id=principal.tenant_id,
        template=template,
        kind=body.kind,
        locale=body.locale,
        variables=body.variables,
        instructions=body.instructions,
    )
    return DraftResponse(title=title, body=body_text, document_id=doc.id)
