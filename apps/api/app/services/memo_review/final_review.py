"""Final Review Before Submission to Najiz — the strict verification gate.

Different from the multi-advisor review: this is a GATE, not advice. Its
output drives whether the dashboard's "Submit to Najiz" button is enabled.

Spec Note 2: the 8 mandatory checks.
    1. basis              — every claim supported by text / facts / document
    2. statutes           — cited statutes are real and correctly applied
    3. facts_names_dates  — names / IDs / dates / amounts internally consistent
    4. requests           — requests logical, connected to facts, well-drafted
    5. procedures         — standing, jurisdiction, time limits, admissibility
    6. contradictions     — no internal contradictions across the memo
    7. hallucination      — no fabricated law or facts; flag unsupported claims
    8. submission_readiness — final READY / READY_WITH_OBS / NOT_READY verdict

Each check fires its own LLM call in parallel — focused prompts produce
higher-quality verification than one omnibus check.

Strict rule (spec): any information / request / inference with no clear
basis = flagged in the output. The aggregator then decides:
    * any check `fail`            → verdict = NOT_READY
    * any check `warn` (and 0 fail) → verdict = READY_WITH_OBSERVATIONS
    * all `pass`                  → verdict = READY
"""
from __future__ import annotations

import concurrent.futures
import json
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.memo_review import (
    FinalReview,
    FinalReviewRiskLevel,
    FinalReviewStatus,
    FinalReviewVerdict,
)
from app.schemas.memo_review import FinalReviewCreate
from app.services.llm import get_llm_provider

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------


CHECK_PREAMBLE = """\
You are a STRICT verification gate for a Saudi-law memo about to be submitted
to the Najiz e-litigation portal. You are NOT an advisor — you do not
suggest improvements or rewrite text. Your job is exactly one thing:

    Detect risk that could embarrass the lawyer if this memo is filed today.

HARD RULES:
  1. Do NOT invent law, facts, parties, dates, or amounts. If you are unsure
     whether a claim is supported, mark it as `warn` with a clear "needs
     human verification" note — never silently assume.
  2. Quote the memo verbatim when you flag a problem (`quote` field).
  3. Be specific: every finding must reference WHERE in the memo (heading,
     paragraph, or distinctive phrase) so the lawyer can jump to it.
  4. If the memo is in Arabic, reply in Arabic. If English, reply in English.
  5. Output STRICTLY conforms to the JSON schema you were given — no prose.
"""


CHECK_SCHEMA = {
    "type": "object",
    "required": ["status", "summary", "findings"],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["pass", "warn", "fail"],
            "description": (
                "pass = nothing material to flag; "
                "warn = needs lawyer attention before submission; "
                "fail = blocker — do NOT submit until fixed."
            ),
        },
        "summary": {
            "type": "string",
            "description": "One-sentence verdict for this check.",
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "message"],
                "properties": {
                    "severity": {"type": "string", "enum": ["info", "warn", "blocker"]},
                    "message": {"type": "string"},
                    "location": {"type": "string", "description": "Where in the memo this issue lives."},
                    "quote": {"type": "string", "description": "Verbatim excerpt from the memo."},
                    "suggested_fix": {"type": "string"},
                },
            },
        },
    },
}


CHECKS: dict[str, dict[str, str]] = {
    "basis": {
        "name_en": "Support / Basis Check",
        "name_ar": "فحص الأساس والاستناد",
        "prompt": (
            "Examine: does every important claim in the memo have a basis? "
            "Does every request have an origin? Is every legal inference supported "
            "by a text, fact, or document?\n\n"
            "Flag (status='warn' or 'fail') any claim that is:\n"
            "  * Asserted as legal fact without a cited basis.\n"
            "  * Inferred from facts that aren't in the memo's narrative.\n"
            "  * Backed by a document that is referenced but not described.\n"
            "  * A request that doesn't trace to a claim in the body.\n\n"
            "status='pass' only when every material claim is anchored."
        ),
    },
    "statutes": {
        "name_en": "Statutes Check",
        "name_ar": "فحص النصوص النظامية",
        "prompt": (
            "Examine: are the cited Saudi statutes correct? Were they used in their "
            "correct place? Is there a missing, misleading, or inappropriate citation?\n\n"
            "Flag any:\n"
            "  * Article number that does not exist in the cited law.\n"
            "  * Citation of a law that is not relevant to the assertion.\n"
            "  * Use of an old (pre-2022/2023) statute when a newer one governs.\n"
            "  * Missing essential citation a court would expect (e.g. asserting "
            "    damages without citing Civil Transactions Law arts 138 / 139).\n"
            "  * Wording that summarizes the statute incorrectly.\n\n"
            "If you are unsure whether a cited article exists, mark it 'warn' with "
            "a 'needs human verification' note — DO NOT silently approve."
        ),
    },
    "facts_names_dates": {
        "name_en": "Facts / Names / Dates / Amounts Check",
        "name_ar": "فحص الوقائع والأسماء والتواريخ والمبالغ",
        "prompt": (
            "Examine internal consistency of: names of parties, ID numbers, dates, "
            "amounts, contract numbers, and the chronological sequence.\n\n"
            "Flag any:\n"
            "  * Name mismatch (e.g. plaintiff named two different ways).\n"
            "  * Date that contradicts another date in the memo.\n"
            "  * Amount that contradicts another amount.\n"
            "  * Contract / case number referenced inconsistently.\n"
            "  * Implausible date (e.g. a hearing scheduled before the lawsuit was filed).\n\n"
            "If a fact is referenced but not anchored anywhere else in the memo, "
            "mark it 'warn' with 'needs human confirmation'."
        ),
    },
    "requests": {
        "name_en": "Requests Check",
        "name_ar": "فحص الطلبات",
        "prompt": (
            "Examine the final requests / claims (الطلبات). Are they logical? Connected "
            "to the facts? Aligned with the legal characterization? Is there a missing, "
            "excessive, or unclear request?\n\n"
            "Flag any:\n"
            "  * Request that doesn't trace back to a claim in the body.\n"
            "  * Request that exceeds what the facts can sustain (e.g. punitive damages "
            "    on a contract claim where Saudi law doesn't allow them).\n"
            "  * Vague request (e.g. 'compensate the plaintiff fairly' with no amount or "
            "    estimation basis).\n"
            "  * Missing request the lawyer almost certainly meant to make."
        ),
    },
    "procedures": {
        "name_en": "Procedures & Formal Admissibility",
        "name_ar": "فحص الإجراءات والقبول الشكلي",
        "prompt": (
            "Examine: standing (الصفة), interest (المصلحة), jurisdiction (الاختصاص), time "
            "limits, admissibility, and any formal point that might prevent acceptance.\n\n"
            "Flag any:\n"
            "  * Jurisdiction issue (wrong court, wrong territory).\n"
            "  * Standing gap (plaintiff not the right party).\n"
            "  * Time-bar concern (statute of limitations possibly expired).\n"
            "  * Missing prerequisite (e.g. mediation not attempted in disputes that require it).\n"
            "  * Missing court-fee acknowledgement or power-of-attorney reference.\n\n"
            "Procedural blockers should be 'fail' — better to halt the submission than "
            "to have the suit dismissed for a formal defect."
        ),
    },
    "contradictions": {
        "name_en": "Internal Contradictions",
        "name_ar": "فحص التناقضات الداخلية",
        "prompt": (
            "Examine: is there a contradiction between the facts and the requests? "
            "Between the beginning of the memo and the end? Between the cited texts "
            "and the desired outcome?\n\n"
            "Flag any:\n"
            "  * Two paragraphs that assert opposite versions of the same fact.\n"
            "  * A legal theory in the body that doesn't match the request.\n"
            "  * A cited statute whose effect contradicts the conclusion drawn from it.\n"
            "  * Internal logical inconsistency."
        ),
    },
    "hallucination": {
        "name_en": "Hallucination / Undocumented Claims",
        "name_ar": "فحص المعلومات غير الموثقة",
        "prompt": (
            "Most important check. Examine: is there any legal or factual information "
            "with no basis in the memo's own facts or the cited Saudi law?\n\n"
            "Flag any:\n"
            "  * Sentence that sounds legal but has no grounding (made-up doctrine).\n"
            "  * Made-up case citation, made-up Royal Decree number, made-up MoJ "
            "    circular number.\n"
            "  * Unjustified analytical leap (\"therefore X\" with no chain of reasoning).\n"
            "  * Claim about Saudi procedure that's not actually how Saudi procedure works.\n\n"
            "BE STRICT: if you cannot verify a specific factual or legal assertion from "
            "what's in the memo itself, mark it 'warn' (or 'fail' if obviously fabricated). "
            "The cost of a false positive is a lawyer double-checking. The cost of a false "
            "negative is a memo with fabricated law going to court."
        ),
    },
    "submission_readiness": {
        "name_en": "Submission Readiness",
        "name_ar": "فحص الجاهزية للتقديم",
        "prompt": (
            "Final check. Assume all previous checks have been performed. Looking at the "
            "memo as a whole, is it READY to be filed at Najiz today?\n\n"
            "Flag any:\n"
            "  * Surface-level issue a clerk will reject (missing party name, missing "
            "    representation declaration, missing prayer for relief).\n"
            "  * Tone that's unprofessional or polemical.\n"
            "  * Missing signature block or attorney bar reference (if expected).\n\n"
            "status='pass' means: a competent Saudi clerk would accept this for filing."
        ),
    },
}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _build_input(review: FinalReview) -> str:
    parts = ["=== MEMO UNDER FINAL REVIEW ===\n", review.memo_text.strip()]
    if review.context:
        parts.append("\n\n=== CONTEXT (parties / facts / claims) ===")
        parts.append(json.dumps(review.context, ensure_ascii=False, indent=2))
    return "\n".join(parts)


def _run_one_check(check_id: str, body_text: str) -> dict:
    provider = get_llm_provider()
    sys_prompt = (
        CHECK_PREAMBLE
        + "\n\nYOUR CHECK: "
        + CHECKS[check_id]["name_en"]
        + " ("
        + CHECKS[check_id]["name_ar"]
        + ")\n\n"
        + CHECKS[check_id]["prompt"]
    )
    return provider.structured(
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": body_text},
        ],
        CHECK_SCHEMA,
        temperature=0.0,
    )


def _aggregate(checks: dict[str, dict]) -> dict:
    """Roll the 8 check results into a single verdict + surfaced lists.

    Decision table (spec):
        any check.status == "fail"     → NOT_READY            risk_level=high
        any check.status == "warn"     → READY_WITH_OBS       risk_level=medium
        all pass                       → READY                risk_level=low
    """
    statuses = [c.get("status", "warn") for c in checks.values()]
    if "fail" in statuses:
        verdict = FinalReviewVerdict.NOT_READY
        risk = FinalReviewRiskLevel.HIGH
    elif "warn" in statuses:
        verdict = FinalReviewVerdict.READY_WITH_OBSERVATIONS
        risk = FinalReviewRiskLevel.MEDIUM
    else:
        verdict = FinalReviewVerdict.READY
        risk = FinalReviewRiskLevel.LOW

    critical_errors: list[dict] = []
    required_mods: list[str] = []
    human_review_points: list[str] = []
    for check_id, c in checks.items():
        for f in c.get("findings", []) or []:
            sev = f.get("severity", "warn")
            msg = (f.get("message") or "").strip()
            loc = (f.get("location") or "").strip()
            quote = (f.get("quote") or "").strip()
            fix = (f.get("suggested_fix") or "").strip()
            entry = {
                "check": check_id,
                "severity": sev,
                "message": msg,
                **({"location": loc} if loc else {}),
                **({"quote": quote} if quote else {}),
                **({"suggested_fix": fix} if fix else {}),
            }
            if sev == "blocker":
                critical_errors.append(entry)
            if fix:
                required_mods.append(fix if fix.endswith(".") else fix + ".")
            if "human" in msg.lower() or "verify" in msg.lower():
                human_review_points.append(msg)

    return {
        "verdict": verdict.value,
        "risk_level": risk.value,
        "critical_errors": critical_errors,
        "required_modifications": list(dict.fromkeys(required_mods))[:20],
        "human_review_points": list(dict.fromkeys(human_review_points))[:20],
    }


def start_final_review(
    db: Session,
    *,
    tenant_id: UUID,
    user_id: UUID | None,
    payload: FinalReviewCreate,
) -> FinalReview:
    fr = FinalReview(
        id=uuid4(),
        tenant_id=tenant_id,
        case_id=payload.case_id,
        memo_review_id=payload.memo_review_id,
        created_by=user_id,
        memo_text=payload.memo_text,
        context=payload.context,
        attached_document_ids=payload.attached_document_ids,
        status=FinalReviewStatus.QUEUED,
    )
    db.add(fr)
    db.commit()
    db.refresh(fr)
    return fr


def run_final_review(final_review_id: UUID, *, max_workers: int = 4) -> None:
    """Execute a queued final review end-to-end."""
    with SessionLocal() as db:
        fr = db.get(FinalReview, final_review_id)
        if fr is None or fr.status not in (FinalReviewStatus.QUEUED, FinalReviewStatus.FAILED):
            return
        fr.status = FinalReviewStatus.RUNNING
        fr.started_at = datetime.now(timezone.utc)
        fr.error = None
        db.commit()
        body_text = _build_input(fr)
        review_id_local = fr.id

    results: dict[str, dict] = {}
    lock = threading.Lock()

    def _worker(check_id: str) -> None:
        try:
            res = _run_one_check(check_id, body_text)
        except Exception as exc:  # noqa: BLE001
            log.exception("final_review_check_failed", check_id=check_id, review_id=str(review_id_local))
            res = {
                "status": "warn",
                "summary": f"Check failed to execute: {type(exc).__name__}",
                "findings": [
                    {
                        "severity": "warn",
                        "message": "This check could not be completed — re-run before submission.",
                    }
                ],
            }
        with lock:
            results[check_id] = res

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_worker, cid) for cid in CHECKS]
        concurrent.futures.wait(futures)

    agg = _aggregate(results)

    with SessionLocal() as db:
        fr = db.get(FinalReview, review_id_local)
        if fr is None:
            return
        fr.checks = results
        fr.verdict = agg["verdict"]
        fr.risk_level = agg["risk_level"]
        fr.critical_errors = agg["critical_errors"]
        fr.required_modifications = agg["required_modifications"]
        fr.human_review_points = agg["human_review_points"]
        fr.status = FinalReviewStatus.DONE
        fr.completed_at = datetime.now(timezone.utc)
        db.commit()
        log.info(
            "final_review_completed",
            review_id=str(review_id_local),
            verdict=agg["verdict"],
            risk_level=agg["risk_level"],
            critical_errors=len(agg["critical_errors"]),
        )
