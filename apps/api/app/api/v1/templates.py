"""Templates: list and get. Tenant + platform-global."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.models import Template
from app.models.template import TemplateKind

router = APIRouter()


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title_en: str
    title_ar: str
    kind: TemplateKind
    is_global: bool
    variables: list


@router.get("", response_model=list[TemplateRead])
def list_templates(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    kind: TemplateKind | None = None,
) -> list[TemplateRead]:
    stmt = select(Template).where(
        or_(Template.tenant_id == principal.tenant_id, Template.is_global.is_(True))
    )
    if kind is not None:
        stmt = stmt.where(Template.kind == kind)
    rows = list(db.execute(stmt.order_by(Template.title_en)).scalars())
    return [TemplateRead.model_validate(r) for r in rows]


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(
    template_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> TemplateRead:
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    if not template.is_global and template.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Template not found.")
    return TemplateRead.model_validate(template)
