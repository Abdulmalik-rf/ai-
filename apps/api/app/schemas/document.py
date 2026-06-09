from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentSource, DocumentStatus
from app.models.template import TemplateKind


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    source: DocumentSource
    status: DocumentStatus
    mime_type: str
    byte_size: int
    page_count: int
    language: str
    case_id: UUID | None
    created_at: datetime

    # When the contract reviewer has been run against this doc we stash the
    # most recent result in extra_metadata so the dashboard can show it
    # again without re-burning AI credits.
    last_contract_review: dict | None = None
    last_contract_review_at: datetime | None = None

    @classmethod
    def model_validate(cls, obj, **kw):  # type: ignore[override]
        # `from_attributes=True` only picks declared attributes, so we have
        # to project the JSONB blob into the response manually.
        instance = super().model_validate(obj, **kw)
        meta = getattr(obj, "extra_metadata", None) or {}
        review = meta.get("last_contract_review")
        if isinstance(review, dict):
            instance.last_contract_review = review.get("result")
            ts = review.get("at")
            if isinstance(ts, str):
                try:
                    instance.last_contract_review_at = datetime.fromisoformat(ts)
                except ValueError:
                    pass
        return instance


class DocumentUploadResponse(BaseModel):
    document: DocumentRead
    upload_id: str  # async job id (Celery task)


class DraftRequest(BaseModel):
    template_id: UUID | None = None
    kind: TemplateKind
    locale: str = Field(default="ar", pattern=r"^(ar|en)$")
    variables: dict = Field(default_factory=dict)
    instructions: str | None = None  # free-form refinement


class DraftResponse(BaseModel):
    title: str
    body: str
    document_id: UUID  # the saved generated document
