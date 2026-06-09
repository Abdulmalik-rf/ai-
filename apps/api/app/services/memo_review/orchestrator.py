"""Memo-review orchestrator — fans out to advisors, runs the final manager.

Flow (spec §4):
    Stage 1  user-supplied case file        → `MemoReviewCreate` schema
    Stage 2  "primary case file" assembly   → `_build_case_file()`
    Stage 3  independent advisor reviews    → `_run_one_advisor()` ×N (parallel)
    Stage 4  collect results                → loop persists each advisor row
    Stage 5  final manager merge            → `_run_final_manager()`

Critical invariants from the spec:
    * Each advisor sees ONLY the primary case file — NEVER another advisor's
      output (spec §3 "independent review", §10 "Rule 2").
    * Only the final manager sees everyone's results (§10 "Rule 3").
    * Each advisor adheres to the fixed output template (§7, §10 "Rule 4").
    * The final manager de-dupes and orders priorities (§10 "Rule 5", §10
      "Rule 6").
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.memo_review import (
    AdvisorAssessment,
    AdvisorImpact,
    MemoReview,
    MemoReviewAdvisor,
    ReviewMode,
    ReviewStatus,
)
from app.schemas.memo_review import MemoReviewCreate
from app.services.llm import get_llm_provider
from app.services.memo_review.advisors import ADVISORS, AdvisorSpec, resolve_advisor_ids

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Stage 2 — assemble the primary case file (spec).
# ---------------------------------------------------------------------------


def _build_case_file(review: MemoReview) -> str:
    """The single canonical payload sent verbatim to every advisor.

    Order matches the spec's recommended sections so advisors see the same
    framing as a real Saudi court briefing memo would receive.
    """
    parts: list[str] = []
    parts.append("=== ملف القضية الأساسي / PRIMARY CASE FILE ===\n")

    parts.append(f"العنوان / Case Title: {review.case_title}")
    if review.case_type:
        parts.append(f"نوع القضية / Case Type: {review.case_type}")

    if review.facts:
        parts.append("\n--- الوقائع / FACTS ---")
        parts.append(review.facts.strip())

    if review.claims:
        parts.append("\n--- الطلبات / CLAIMS ---")
        parts.append(review.claims.strip())

    parts.append("\n--- المذكرة الحالية / CURRENT MEMO ---")
    parts.append(review.memo_text.strip())

    if review.notes:
        parts.append("\n--- ملاحظات الموكل / CLIENT NOTES ---")
        parts.append(review.notes.strip())

    parts.append(
        "\n--- نقاط المراجعة / POINTS TO REVIEW ---\n"
        "Review the memo from YOUR assigned angle only. Produce structured "
        "output per the schema you were given."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Stage 3 — single-advisor run.
# ---------------------------------------------------------------------------


def _run_one_advisor(
    advisor_spec: AdvisorSpec,
    case_file_text: str,
) -> dict:
    """Issue one LLM call for a single advisor; return its structured JSON.

    Uses the global `llm_provider` (Gemini by default after the 2026-06-06
    cutover). Both Gemini and ChatGPT-OAuth providers expose `.structured()`
    with identical signatures so this code is provider-agnostic.
    """
    provider = get_llm_provider()
    messages = [
        {"role": "system", "content": advisor_spec.system_prompt},
        {"role": "user", "content": case_file_text},
    ]
    return provider.structured(messages, advisor_spec.schema, temperature=0.2)


def _coerce_advisor_output(raw: dict) -> dict:
    """Normalize a raw advisor response into safe ranges.

    LLMs sometimes return more observations/risks/recs than the spec allows.
    Clip rather than reject so a slightly over-eager run isn't wasted.
    """
    def _clip(seq: object, lo: int, hi: int) -> list[str]:
        if not isinstance(seq, list):
            return []
        out = [str(x) for x in seq if str(x).strip()]
        return out[:hi] if len(out) >= lo else out

    out: dict = {
        "assessment": _safe_enum(raw.get("assessment"), {a.value for a in AdvisorAssessment}, "medium"),
        "impact_level": _safe_enum(raw.get("impact_level"), {a.value for a in AdvisorImpact}, "medium"),
        "observations": _clip(raw.get("observations"), 3, 5),
        "risk_points": _clip(raw.get("risk_points"), 1, 3),
        "recommendations": _clip(raw.get("recommendations"), 2, 4),
        "extra": raw.get("extra") if isinstance(raw.get("extra"), dict) else None,
    }
    return out


def _safe_enum(val: object, allowed: set[str], default: str) -> str:
    s = str(val).lower().strip() if val is not None else ""
    return s if s in allowed else default


# ---------------------------------------------------------------------------
# Stage 5 — final manager merge.
# ---------------------------------------------------------------------------

FINAL_MANAGER_PROMPT = """\
You are the FINAL REVIEW MANAGER for a multi-advisor Saudi-law memo review.

You have just received 3–10 INDEPENDENT advisor reports. None of them saw
each other. Your job (spec §6) is to:

  1. Read all reports.
  2. Remove repetition across advisors.
  3. Resolve conflicts (when two advisors disagree, prefer the one with
     concrete grounding in the memo / facts over generic advice).
  4. Order priorities by impact-on-outcome (not by which advisor raised
     them — the same priority can appear in multiple reports).
  5. Produce a single executive output, not a long report.

OUTPUT (strict JSON, no prose):
{
  "general_assessment": {
    "case_strength":   "strong"|"medium"|"weak",
    "memo_strength":   "strong"|"medium"|"weak",
    "risk_level":      "low"|"medium"|"high",
    "memo_readiness":  "ready"|"ready_with_observations"|"not_ready"
  },
  "top_priorities":            [ "1st modification …", … up to 5 ],
  "summary_of_observations":   [ deduped cross-advisor observations, max 8 ],
  "remaining_risks":           [ risks the lawyer must still address, max 5 ],
  "final_recommendation":      "one-paragraph executive recommendation",
  "final_alerts":              [ general alerts, max 4 ],
  "human_review_points":       [ what must be confirmed by a human, max 5 ]
}

LANGUAGE: match the memo's language (Arabic memo → Arabic output; English
memo → English; mixed → Arabic). Be concise. Quality over volume.
"""

FINAL_MANAGER_SCHEMA: dict = {
    "type": "object",
    "required": ["general_assessment", "top_priorities", "final_recommendation"],
    "properties": {
        "general_assessment": {
            "type": "object",
            "required": ["case_strength", "memo_strength", "risk_level", "memo_readiness"],
            "properties": {
                "case_strength": {"type": "string", "enum": ["strong", "medium", "weak"]},
                "memo_strength": {"type": "string", "enum": ["strong", "medium", "weak"]},
                "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                "memo_readiness": {
                    "type": "string",
                    "enum": ["ready", "ready_with_observations", "not_ready"],
                },
            },
        },
        "top_priorities": {"type": "array", "minItems": 1, "maxItems": 5, "items": {"type": "string"}},
        "summary_of_observations": {"type": "array", "maxItems": 8, "items": {"type": "string"}},
        "remaining_risks": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
        "final_recommendation": {"type": "string"},
        "final_alerts": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
        "human_review_points": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
    },
}


REVISED_MEMO_PROMPT = """\
You are the FINAL REVIEW MANAGER's drafting hand. You have just produced
a merged executive summary. The lawyer asked for the REVISED VERSION of the
memo that addresses every "top_priority" you identified.

HARD RULES:
  1. Preserve the lawyer's voice, structure, and section headings.
  2. Only change what your priorities require — do not rewrite untouched
     sections.
  3. Do NOT invent facts, parties, dates, or amounts not in the original.
  4. Keep the language of the original memo (Arabic → Arabic; English → English).
  5. Output is the FULL revised memo as plain text — no commentary,
     no JSON, no markdown wrappers.
"""


def _run_final_manager(
    review: MemoReview,
    advisor_outputs: list[dict],
) -> tuple[dict, str | None]:
    """Run the manager merge + (optionally) produce the revised memo."""
    provider = get_llm_provider()

    # Build the manager input: case file + every advisor's structured report.
    advisor_block = []
    for o in advisor_outputs:
        spec = ADVISORS[o["advisor_id"]]
        advisor_block.append(
            f"=== {spec.name_en} ({spec.name_ar}) ===\n"
            + json.dumps(
                {
                    "assessment": o.get("assessment"),
                    "impact_level": o.get("impact_level"),
                    "observations": o.get("observations") or [],
                    "risk_points": o.get("risk_points") or [],
                    "recommendations": o.get("recommendations") or [],
                    "extra": o.get("extra") or {},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    manager_input = (
        _build_case_file(review)
        + "\n\n=== ADVISOR REPORTS ===\n\n"
        + "\n\n".join(advisor_block)
    )

    merged = provider.structured(
        [
            {"role": "system", "content": FINAL_MANAGER_PROMPT},
            {"role": "user", "content": manager_input},
        ],
        FINAL_MANAGER_SCHEMA,
        temperature=0.1,
    )

    revised: str | None = None
    if review.want_revised_memo:
        # Second LLM call: produce the revised memo grounded in `merged`.
        revised_resp = provider.chat(
            [
                {"role": "system", "content": REVISED_MEMO_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "ORIGINAL MEMO:\n"
                        + review.memo_text
                        + "\n\nPRIORITIES TO ADDRESS:\n"
                        + json.dumps(merged.get("top_priorities", []), ensure_ascii=False, indent=2)
                    ),
                },
            ],
            temperature=0.2,
        )
        revised = revised_resp.content.strip() or None

    return merged, revised


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def start_memo_review(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID | None,
    payload: MemoReviewCreate,
) -> MemoReview:
    """Create the review row + queued advisor rows, return immediately.

    Caller is responsible for kicking off `run_memo_review(review.id)` —
    typically via `BackgroundTasks` (sync API) or a Celery dispatch.
    """
    advisor_ids = resolve_advisor_ids(payload.mode, payload.selected_advisors)
    if not advisor_ids:
        raise ValueError(
            "No callable advisors for this mode. (Phase 1 ships 4 advisors — "
            "characterization, evidence, procedures, drafting. Pick those via "
            "custom mode, or wait for Phase 2/3 to upgrade standard/deep.)"
        )

    review = MemoReview(
        id=uuid4(),
        tenant_id=tenant_id,
        case_id=payload.case_id,
        created_by=user_id,
        case_title=payload.case_title,
        case_type=payload.case_type,
        facts=payload.facts,
        claims=payload.claims,
        memo_text=payload.memo_text,
        notes=payload.notes,
        mode=ReviewMode(payload.mode),
        selected_advisors=payload.selected_advisors,
        want_revised_memo=payload.want_revised_memo,
        attached_document_ids=payload.attached_document_ids,
        status=ReviewStatus.QUEUED,
    )
    db.add(review)
    db.flush()

    for aid in advisor_ids:
        db.add(
            MemoReviewAdvisor(
                id=uuid4(),
                review_id=review.id,
                tenant_id=tenant_id,
                advisor_id=aid,
                status=ReviewStatus.QUEUED,
            )
        )

    db.commit()
    db.refresh(review)
    return review


def run_memo_review(review_id: UUID, *, max_workers: int = 4) -> None:
    """Execute a queued review end-to-end.

    Opens its own DB session — safe to call from a Celery worker, a
    FastAPI BackgroundTask, or a CLI script. Updates statuses incrementally
    so the GET endpoint shows partial progress while advisors are still
    running.
    """
    # Each thread needs its own DB session — never share a Session across
    # threads (SQLAlchemy isn't thread-safe).
    with SessionLocal() as db:
        review = db.get(MemoReview, review_id)
        if review is None:
            log.warning("memo_review_not_found", review_id=str(review_id))
            return
        if review.status not in (ReviewStatus.QUEUED, ReviewStatus.FAILED):
            log.warning(
                "memo_review_not_runnable",
                review_id=str(review_id),
                status=str(review.status),
            )
            return
        review.status = ReviewStatus.RUNNING
        review.started_at = datetime.now(timezone.utc)
        review.error = None
        db.commit()

        advisor_rows = (
            db.execute(
                select(MemoReviewAdvisor).where(MemoReviewAdvisor.review_id == review_id)
            )
            .scalars()
            .all()
        )
        case_file_text = _build_case_file(review)
        review_id_local = review.id
        tenant_id_local = review.tenant_id

    # --- Stage 3: independent advisor reviews (parallel) ------------------
    # Each advisor gets its own thread + its own DB session.

    advisor_outputs: list[dict] = []
    output_lock = threading.Lock()

    def _worker(adv_row_id: UUID, advisor_id: str) -> None:
        """Run one advisor in its own session/thread."""
        with SessionLocal() as worker_db:
            row = worker_db.get(MemoReviewAdvisor, adv_row_id)
            if row is None:
                return
            row.status = ReviewStatus.RUNNING
            row.started_at = datetime.now(timezone.utc)
            worker_db.commit()

            try:
                spec = ADVISORS[advisor_id]
                raw = _run_one_advisor(spec, case_file_text)
                norm = _coerce_advisor_output(raw)
                row.assessment = norm["assessment"]
                row.impact_level = norm["impact_level"]
                row.observations = norm["observations"]
                row.risk_points = norm["risk_points"]
                row.recommendations = norm["recommendations"]
                row.extra = norm["extra"]
                row.raw_response = raw
                row.status = ReviewStatus.DONE
                row.completed_at = datetime.now(timezone.utc)
                worker_db.commit()

                with output_lock:
                    advisor_outputs.append({"advisor_id": advisor_id, **norm})

            except Exception as exc:  # noqa: BLE001
                log.exception("advisor_failed", advisor_id=advisor_id, review_id=str(review_id_local))
                row.status = ReviewStatus.FAILED
                row.error = f"{type(exc).__name__}: {exc}"[:2000]
                row.completed_at = datetime.now(timezone.utc)
                worker_db.commit()

    # Cap concurrent advisors — free-tier Gemini rate-limits hard on Pro.
    # `max_workers=4` is fine for Phase-1's 4 advisors; bump for deep mode.
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [
            ex.submit(_worker, row.id, row.advisor_id)
            for row in advisor_rows
            if row.status in (ReviewStatus.QUEUED, ReviewStatus.FAILED)
        ]
        concurrent.futures.wait(futures)

    # --- Stage 4 + 5: collect & run final manager -------------------------

    with SessionLocal() as db:
        review = db.get(MemoReview, review_id_local)
        if review is None:
            return

        # Did at least one advisor succeed? If not, fail the review.
        rows = (
            db.execute(
                select(MemoReviewAdvisor).where(MemoReviewAdvisor.review_id == review_id_local)
            )
            .scalars()
            .all()
        )
        done_outputs = []
        for r in rows:
            if r.status == ReviewStatus.DONE:
                done_outputs.append(
                    {
                        "advisor_id": r.advisor_id,
                        "assessment": r.assessment,
                        "impact_level": r.impact_level,
                        "observations": r.observations or [],
                        "risk_points": r.risk_points or [],
                        "recommendations": r.recommendations or [],
                        "extra": r.extra,
                    }
                )

        if not done_outputs:
            review.status = ReviewStatus.FAILED
            review.error = "All advisors failed — see per-advisor rows for details."
            review.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        try:
            merged, revised = _run_final_manager(review, done_outputs)
            review.final_summary = merged
            review.revised_memo = revised
            review.status = ReviewStatus.DONE
            review.completed_at = datetime.now(timezone.utc)
            db.commit()
            log.info(
                "memo_review_completed",
                review_id=str(review_id_local),
                tenant_id=str(tenant_id_local),
                advisors_done=len(done_outputs),
                advisors_failed=len(rows) - len(done_outputs),
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("final_manager_failed", review_id=str(review_id_local))
            review.status = ReviewStatus.FAILED
            review.error = f"Final manager failed: {type(exc).__name__}: {exc}"[:2000]
            review.completed_at = datetime.now(timezone.utc)
            db.commit()
