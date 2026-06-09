"""Case analysis service.

Reads all documents attached to a case PLUS the chronological history of
court sessions (kind, status, court/judge, notes, recorded outcome) and
asks the LLM for a structured analysis. The result is cached on
`cases.ai_analysis` so the dashboard can display it without re-running
the model.

Hearings are critical context the previous version of this service
ignored — the lawyer's account of what was decided in court is often
the single most relevant input to a strategy recommendation.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Case, Document, Hearing
from app.schemas.case import CaseAnalysisResponse
from app.services.document_processor import parse
from app.services.llm import get_llm_provider
from app.services.prompts import CASE_ANALYSIS_SCHEMA, case_analysis_system
from app.services.storage import download_to_memory

log = get_logger(__name__)

MAX_CHARS_PER_DOC = 40_000
MAX_TOTAL_CHARS = 120_000
MAX_CHARS_PER_HEARING = 4_000


def analyze_case(
    db: Session,
    *,
    case: Case,
    locale: str = "ar",
) -> CaseAnalysisResponse:
    docs = list(
        db.execute(
            select(Document).where(
                Document.tenant_id == case.tenant_id,
                Document.case_id == case.id,
            )
        ).scalars()
    )

    pieces: list[str] = []
    total = 0
    for doc in docs:
        try:
            raw = download_to_memory(doc.storage_key)
            pages = parse(raw, doc.mime_type)
            text = "\n".join(t for _, t in pages)[:MAX_CHARS_PER_DOC]
            block = f"=== {doc.title} ===\n{text}"
            if total + len(block) > MAX_TOTAL_CHARS:
                break
            pieces.append(block)
            total += len(block)
        except Exception:  # noqa: BLE001
            log.exception("case_doc_load_failed", document_id=str(doc.id))

    file_block = "\n\n".join(pieces) or (
        "لا توجد مستندات مرفقة." if locale == "ar" else "No attached documents."
    )

    # --- Hearings: chronological log of what happened in court -----------
    # Sorted oldest→newest so the LLM can follow the procedural arc. The
    # recorded outcome / lawyer notes are the most analytically valuable
    # part — if you don't tell the model what the judge said, it can't
    # build a strategy that reflects reality.
    hearings = list(
        db.execute(
            select(Hearing)
            .where(
                Hearing.tenant_id == case.tenant_id,
                Hearing.case_id == case.id,
            )
            .order_by(Hearing.scheduled_at.asc())
        ).scalars()
    )

    if hearings:
        hearing_lines: list[str] = []
        for h in hearings:
            when = h.scheduled_at.isoformat() if h.scheduled_at else "—"
            header = f"[{when}] {h.kind} · {h.status}"
            details = []
            if h.court_name:
                details.append(
                    f"المحكمة: {h.court_name}"
                    if locale == "ar"
                    else f"Court: {h.court_name}"
                )
            if h.court_circuit:
                details.append(
                    f"الدائرة: {h.court_circuit}"
                    if locale == "ar"
                    else f"Circuit: {h.court_circuit}"
                )
            if h.judge_name:
                details.append(
                    f"القاضي: {h.judge_name}"
                    if locale == "ar"
                    else f"Judge: {h.judge_name}"
                )
            if h.opposing_counsel:
                details.append(
                    f"محامي الخصم: {h.opposing_counsel}"
                    if locale == "ar"
                    else f"Opposing counsel: {h.opposing_counsel}"
                )
            notes = (h.notes or "").strip()
            outcome = (h.outcome or "").strip()
            block = [header]
            if details:
                block.append(" · ".join(details))
            if notes:
                block.append(
                    ("ملاحظات: " if locale == "ar" else "Notes: ")
                    + notes[:MAX_CHARS_PER_HEARING]
                )
            if outcome:
                block.append(
                    ("النتيجة: " if locale == "ar" else "Outcome: ")
                    + outcome[:MAX_CHARS_PER_HEARING]
                )
            hearing_lines.append("\n".join(block))
        hearings_section = "\n\n".join(hearing_lines)
    else:
        hearings_section = (
            "لم تُسجَّل جلسات بعد." if locale == "ar" else "No hearings logged yet."
        )

    # `case.domain` is declared as `Mapped[LegalDomain]` but SQLAlchemy
    # returns it as a plain string from the database; `.value` then blows up
    # with `AttributeError: 'str' object has no attribute 'value'`. Coerce
    # via str() so this works whether it's a StrEnum instance or a string.
    domain = str(case.domain)
    case_brief = (
        f"المرجع: {case.reference}\nالعنوان: {case.title}\nالوصف: {case.description or ''}\nالمجال: {domain}\n"
        if locale == "ar"
        else f"Reference: {case.reference}\nTitle: {case.title}\nDescription: {case.description or ''}\nDomain: {domain}\n"
    )

    hearings_header = (
        "## سجل الجلسات (الأقدم في الأعلى)"
        if locale == "ar"
        else "## Hearing log (oldest first)"
    )
    files_header = (
        "## المستندات المرفقة"
        if locale == "ar"
        else "## Attached documents"
    )

    user_prompt = (
        case_brief
        + "\n"
        + hearings_header
        + "\n"
        + hearings_section
        + "\n\n"
        + files_header
        + "\n"
        + file_block
    )

    llm = get_llm_provider()
    result = llm.structured(
        messages=[
            {"role": "system", "content": case_analysis_system(locale)},
            {"role": "user", "content": user_prompt},
        ],
        schema=CASE_ANALYSIS_SCHEMA,
        temperature=0.1,
    )

    case.ai_analysis = {**result, "locale": locale}
    db.add(case)
    db.commit()

    return CaseAnalysisResponse(
        case_id=case.id,
        summary=result.get("summary", ""),
        legal_issues=result.get("legal_issues", []),
        suggested_strategy=result.get("suggested_strategy", []),
        relevant_laws=result.get("relevant_laws", []),
        risk_assessment=result.get("risk_assessment", ""),
        locale=locale,
    )
