"""Contract review service.

Walks the document text through the LLM with a strict JSON schema, then
returns a typed response. Model-side errors (malformed JSON) are caught and
returned as a single 'critical' finding so the UI never sees an empty review.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import Document
from app.schemas.contract import (
    ContractAdvisorOpinion,
    ContractFinding,
    ContractReviewResponse,
    ContractSuggestion,
)
from app.services.contract_advisors import run_panel
from app.services.document_processor import parse
from app.services.storage import download_to_memory

log = get_logger(__name__)


def _coerce_findings(items: object) -> list[ContractFinding]:
    out: list[ContractFinding] = []
    for f in items if isinstance(items, list) else []:
        if not isinstance(f, dict):
            continue
        try:
            out.append(ContractFinding(
                severity=f.get("severity", "info"),
                category=str(f.get("category", "general")),
                title=str(f.get("title", "")),
                description=str(f.get("description", "")),
                clause_excerpt=f.get("clause_excerpt"),
                page_number=f.get("page_number"),
            ))
        except Exception:  # noqa: BLE001
            continue
    return out


def review_contract(
    db: Session,
    *,
    document: Document,
    locale: str = "ar",
    mode: str = "standard",
) -> ContractReviewResponse:
    """Multi-advisor contract review.

    A panel of specialized advisors (risk / Saudi-law compliance / fairness /
    missing-clauses, + termination & drafting in deep mode) each read the
    contract independently; a synthesizer merges them into one prioritized
    review. Falls back to a single 'critical' finding if the panel errors so
    the UI never sees an empty review.
    """
    raw = download_to_memory(document.storage_key)
    pages = parse(raw, document.mime_type)
    full_text = "\n\n".join(
        f"--- Page {p} ---\n{txt}" for p, txt in pages if txt.strip()
    )
    full_text = full_text[:80_000]

    try:
        advisor_opinions, synthesis = run_panel(full_text, locale=locale, mode=mode)
    except Exception as exc:  # noqa: BLE001
        log.exception("contract_review_failed", document_id=str(document.id))
        return ContractReviewResponse(
            document_id=document.id,
            summary=("تعذر تحليل العقد آليًا." if locale == "ar" else "Automated review failed."),
            findings=[ContractFinding(severity="critical", category="system", title="Analysis error", description=str(exc))],
            suggestions=[],
            missing_clauses=[],
            risk_score=0,
            locale=locale,
        )

    advisors = [
        ContractAdvisorOpinion(
            advisor_id=a["advisor_id"],
            name=a["name"],
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
                    title=str(s.get("title", "")),
                    rationale=str(s.get("rationale", "")),
                    suggested_clause=str(s.get("suggested_clause", "")),
                ))
            except Exception:  # noqa: BLE001
                continue

    return ContractReviewResponse(
        document_id=document.id,
        summary=synthesis.get("summary", ""),
        findings=_coerce_findings(synthesis.get("findings")),
        suggestions=suggestions,
        missing_clauses=[str(m) for m in (synthesis.get("missing_clauses") or []) if str(m).strip()],
        risk_score=int(synthesis.get("risk_score", 0) or 0),
        locale=locale,
        advisors=advisors,
        party_favorability=synthesis.get("party_favorability"),
    )
