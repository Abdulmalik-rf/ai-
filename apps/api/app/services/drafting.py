"""Document drafting (templates → final document).

Templates can be 'fill-in' (variable substitution) or 'AI-augmented' where the
LLM is asked to generate prose between the variable markers. We also save the
result back as a generated `Document` row so it shows up in the user's
documents list.
"""
from __future__ import annotations

import re
import uuid
from io import BytesIO
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Document, DocumentSource, DocumentStatus, Template
from app.models.template import TemplateKind
from app.services.llm import get_llm_provider
from app.services.prompts import drafting_system
from app.services.storage import storage_key_for, upload_fileobj

VAR_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


def _render(body: str, variables: dict) -> str:
    return VAR_RE.sub(lambda m: str(variables.get(m.group(1), m.group(0))), body)


def draft_document(
    db: Session,
    *,
    tenant_id: UUID,
    template: Template | None,
    kind: TemplateKind,
    locale: str,
    variables: dict,
    instructions: str | None,
) -> tuple[str, str, Document]:
    """Returns (title, body, persisted Document row)."""
    base_body = ""
    base_title = kind.value

    if template is not None:
        base_body = template.body_ar if locale == "ar" else template.body_en
        base_title = template.title_ar if locale == "ar" else template.title_en
        base_body = _render(base_body, variables)

    user_msg = (
        ("الكيان المطلوب صياغته: " if locale == "ar" else "Document kind: ")
        + kind.value
        + "\n"
    )
    if base_body:
        user_msg += (
            ("القاعدة المرجعية:\n" if locale == "ar" else "Base template:\n")
            + base_body
            + "\n"
        )
    if variables:
        user_msg += (
            ("المتغيرات:\n" if locale == "ar" else "Variables:\n")
            + "\n".join(f"- {k}: {v}" for k, v in variables.items())
            + "\n"
        )
    if instructions:
        user_msg += (
            ("تعليمات إضافية: " if locale == "ar" else "Extra instructions: ")
            + instructions
        )

    llm = get_llm_provider()
    resp = llm.chat(
        [
            {"role": "system", "content": drafting_system(locale)},
            {"role": "user", "content": user_msg},
        ]
    )
    body = resp.content.strip()

    # Persist as a generated document
    doc_id = uuid.uuid4()
    storage_key = storage_key_for(tenant_id, doc_id, f"{base_title}.txt")
    upload_fileobj(storage_key, BytesIO(body.encode("utf-8")), "text/plain")

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        title=base_title,
        source=DocumentSource.GENERATED,
        status=DocumentStatus.INDEXED,
        storage_key=storage_key,
        mime_type="text/plain",
        byte_size=len(body.encode("utf-8")),
        page_count=1,
        language=locale,
        extra_metadata={"kind": kind.value, "template_id": str(template.id) if template else None},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return base_title, body, doc
