"""Consultation orchestrator — framing → grounding → advisory panel →
synthesis → verification.

Mirrors the memo-review fan-out (one thread + one DB session per advisor),
but the stages are advisory rather than adversarial:

    Stage 1  Framing      — restructure the raw question (1 LLM call).
    Stage 2  Grounding    — RAG retrieval over the corpus (no LLM; SQL+vectors).
    Stage 3  Advisory     — N independent advisors (parallel).
    Stage 4  Synthesis    — merge into one client-ready legal opinion.
    Stage 5  Verification — strict gate: every citation/claim grounded?
"""
from __future__ import annotations

import concurrent.futures
import json
import threading
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.consultation import (
    Consultation,
    ConsultationAdvisor,
    ConsultationConfidence,
    ConsultationMode,
    ConsultationStatus,
)
from app.schemas.consultation import ConsultationCreate
from app.services.consultation.advisors import ADVISORS, resolve_advisor_ids
from app.services.llm import get_llm_provider
from app.services.agent_tools import resolve_platform_tenant_id
from app.services.rag import retrieve

log = get_logger(__name__)


# ── Stage 1: framing ───────────────────────────────────────────────────

FRAMING_PROMPT = """\
You are the intake analyst for a Saudi legal-consultation engine. Restructure
the client's raw question into a clean brief for the advisory panel.

Output STRICT JSON:
{
  "refined_questions": [ "the precise legal question(s), 1-3" ],
  "material_facts":    [ "the facts that matter, extracted from the situation" ],
  "domain":            "commercial|labor|family|criminal|real_estate|administrative|ip|tax_zakat|data_protection|other",
  "missing_info":      [ "critical facts the client did NOT provide that a lawyer would need" ],
  "search_queries":    [ "2-4 Arabic search phrases to find the governing statutes" ]
}
Match the client's language. Do not answer the question — only frame it.
"""

FRAMING_SCHEMA = {
    "type": "object",
    "required": ["refined_questions", "material_facts", "domain", "missing_info", "search_queries"],
    "properties": {
        "refined_questions": {"type": "array", "items": {"type": "string"}},
        "material_facts": {"type": "array", "items": {"type": "string"}},
        "domain": {"type": "string"},
        "missing_info": {"type": "array", "items": {"type": "string"}},
        "search_queries": {"type": "array", "items": {"type": "string"}},
    },
}


def _run_framing(consultation: Consultation) -> dict:
    provider = get_llm_provider()
    user = f"QUESTION:\n{consultation.question}\n"
    if consultation.situation:
        user += f"\nSITUATION:\n{consultation.situation}\n"
    if consultation.client_type:
        user += f"\nCLIENT TYPE: {consultation.client_type}\n"
    return provider.structured(
        [{"role": "system", "content": FRAMING_PROMPT}, {"role": "user", "content": user}],
        FRAMING_SCHEMA,
        temperature=0.1,
    )


# ── Stage 2: grounding (RAG) ────────────────────────────────────────────


def _run_grounding(db: Session, consultation: Consultation, framing: dict) -> dict:
    """Retrieve corpus passages for the framed queries. No LLM — pure search."""
    platform_id = resolve_platform_tenant_id(db)
    queries = framing.get("search_queries") or [consultation.question]
    domain = framing.get("domain")
    seen: set[str] = set()
    citations: list[dict] = []
    passages: list[str] = []
    for q in queries[:4]:
        try:
            chunks = retrieve(
                db,
                query=q,
                tenant_id=consultation.tenant_id,
                platform_tenant_id=platform_id,
                top_k=4,
                domain=domain,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("consultation_grounding_retrieve_failed", error=str(exc))
            continue
        for c in chunks:
            key = f"{c.document_id}:{c.page_number}"
            if key in seen:
                continue
            seen.add(key)
            citations.append({
                "label": c.citation_label(),
                "statute": c.title,
                "article": c.article_number,
                "domain": c.legal_domain,
            })
            passages.append(f"[{c.citation_label()}]\n{c.content[:700]}")
    return {"citations": citations[:12], "passages": passages[:10]}


# ── Stage 3: one advisor ────────────────────────────────────────────────


def _build_brief(consultation: Consultation, framing: dict, grounding: dict) -> str:
    parts = ["=== CLIENT CONSULTATION BRIEF ===\n"]
    parts.append(f"QUESTION:\n{consultation.question}")
    if consultation.situation:
        parts.append(f"\nSITUATION:\n{consultation.situation}")
    if consultation.client_type:
        parts.append(f"\nCLIENT TYPE: {consultation.client_type}")
    rq = framing.get("refined_questions") or []
    if rq:
        parts.append("\nREFINED QUESTIONS:\n- " + "\n- ".join(rq))
    mf = framing.get("material_facts") or []
    if mf:
        parts.append("\nMATERIAL FACTS:\n- " + "\n- ".join(mf))
    mi = framing.get("missing_info") or []
    if mi:
        parts.append("\nMISSING INFO (not provided by client):\n- " + "\n- ".join(mi))
    passages = grounding.get("passages") or []
    if passages:
        parts.append(
            "\n=== RELEVANT SAUDI-LAW PASSAGES (from the firm corpus) ===\n"
            + "\n\n".join(passages)
            + "\n(Use these to ground your answer. If they don't cover the point, "
            "rely on your Saudi-law knowledge but mark uncertainty in caveats.)"
        )
    return "\n".join(parts)


def _run_one_advisor(advisor_id: str, brief: str) -> dict:
    provider = get_llm_provider()
    spec = ADVISORS[advisor_id]
    return provider.structured(
        [{"role": "system", "content": spec.system_prompt}, {"role": "user", "content": brief}],
        spec.schema,
        temperature=0.2,
    )


def _coerce(raw: dict) -> dict:
    def _list(x):
        return [str(i) for i in x if str(i).strip()] if isinstance(x, list) else []
    conf = str(raw.get("confidence", "medium")).lower()
    if conf not in ("high", "medium", "low"):
        conf = "medium"
    return {
        "position": str(raw.get("position", "")).strip() or None,
        "confidence": conf,
        "key_points": _list(raw.get("key_points")),
        "citations": raw.get("citations") if isinstance(raw.get("citations"), list) else [],
        "caveats": _list(raw.get("caveats")),
        "extra": raw.get("extra") if isinstance(raw.get("extra"), dict) else None,
    }


# ── Stage 4: synthesis ──────────────────────────────────────────────────

SYNTH_PROMPT = """\
You are the SENIOR PARTNER synthesizing a client-ready legal opinion from an
advisory panel. You received 4-5 independent advisor inputs (statutory, risk,
options, procedural, and possibly a devil's advocate). Merge them — remove
repetition, resolve conflicts (prefer concrete, grounded reasoning), and
produce ONE coherent opinion.

Output STRICT JSON:
{
  "executive_answer":   "Clear answer + one paragraph. Lead with yes/no/it-depends.",
  "answer_disposition": "yes|no|depends|conditional",
  "legal_basis":        [ {"statute":"...","article":"...","summary":"..."} ],
  "analysis":           "the reasoning, 1-3 short paragraphs",
  "options":            [ {"option":"...","pros":["..."],"cons":["..."],"rank":1} ],
  "risks":              [ "the key risks the client must understand" ],
  "recommended_action": "what you advise the client to do",
  "caveats":            [ "limits of this opinion" ],
  "human_review_points":[ "what a licensed lawyer must confirm before acting" ]
}

RULES:
  - Do NOT introduce statutes/articles no advisor cited. If unsure an article
    exists, omit it or move it to human_review_points.
  - Match the client's language.
  - Be decisive but honest about uncertainty.
"""

SYNTH_SCHEMA = {
    "type": "object",
    "required": ["executive_answer", "answer_disposition", "recommended_action"],
    "properties": {
        "executive_answer": {"type": "string"},
        "answer_disposition": {"type": "string", "enum": ["yes", "no", "depends", "conditional"]},
        "legal_basis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statute": {"type": "string"},
                    "article": {"type": "string"},
                    "summary": {"type": "string"},
                },
            },
        },
        "analysis": {"type": "string"},
        "options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "option": {"type": "string"},
                    "pros": {"type": "array", "items": {"type": "string"}},
                    "cons": {"type": "array", "items": {"type": "string"}},
                    "rank": {"type": "integer"},
                },
            },
        },
        "risks": {"type": "array", "items": {"type": "string"}},
        "recommended_action": {"type": "string"},
        "caveats": {"type": "array", "items": {"type": "string"}},
        "human_review_points": {"type": "array", "items": {"type": "string"}},
    },
}


# ── Stage 5: verification gate ──────────────────────────────────────────

VERIFY_PROMPT = """\
You are a STRICT verification gate for a legal opinion about to be sent to a
client. You do not improve the opinion — you flag risk.

Given the opinion + the corpus passages that were available, check:
  1. Does every cited statute/article plausibly exist and apply? (Flag
     anything you cannot corroborate — fabricated article numbers are the
     biggest danger.)
  2. Is every key assertion grounded in the facts or the cited law, or is it
     an unsupported leap?
  3. Is the recommended action consistent with the stated risks?

Output STRICT JSON:
{
  "verdict": "safe|safe_with_caveats|needs_review",
  "confidence_level": "high|medium|low",
  "unsupported_claims": [ {"claim":"...","why":"..."} ],
  "notes": "one-sentence overall assessment"
}
verdict=needs_review if any cited article looks fabricated or a core claim is
unsupported. Match the opinion's language in messages.
"""

VERIFY_SCHEMA = {
    "type": "object",
    "required": ["verdict", "confidence_level"],
    "properties": {
        "verdict": {"type": "string", "enum": ["safe", "safe_with_caveats", "needs_review"]},
        "confidence_level": {"type": "string", "enum": ["high", "medium", "low"]},
        "unsupported_claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"claim": {"type": "string"}, "why": {"type": "string"}},
            },
        },
        "notes": {"type": "string"},
    },
}


def _run_synthesis(consultation: Consultation, framing: dict, grounding: dict, advisor_outputs: list[dict]) -> dict:
    provider = get_llm_provider()
    blocks = []
    for o in advisor_outputs:
        spec = ADVISORS[o["advisor_id"]]
        blocks.append(
            f"=== {spec.name_en} ({spec.name_ar}) ===\n"
            + json.dumps({k: o.get(k) for k in ("position", "confidence", "key_points", "citations", "caveats", "extra")}, ensure_ascii=False, indent=2)
        )
    user = _build_brief(consultation, framing, grounding) + "\n\n=== ADVISOR INPUTS ===\n\n" + "\n\n".join(blocks)
    return provider.structured(
        [{"role": "system", "content": SYNTH_PROMPT}, {"role": "user", "content": user}],
        SYNTH_SCHEMA,
        temperature=0.1,
    )


def _run_verification(opinion: dict, grounding: dict) -> dict:
    provider = get_llm_provider()
    passages = "\n\n".join(grounding.get("passages") or [])[:6000]
    user = (
        "OPINION:\n" + json.dumps(opinion, ensure_ascii=False, indent=2)
        + "\n\nAVAILABLE CORPUS PASSAGES:\n" + (passages or "(none retrieved)")
    )
    return provider.structured(
        [{"role": "system", "content": VERIFY_PROMPT}, {"role": "user", "content": user}],
        VERIFY_SCHEMA,
        temperature=0.0,
    )


# ── Public entry points ─────────────────────────────────────────────────


def start_consultation(db: Session, *, tenant_id: UUID, user_id: UUID | None, payload: ConsultationCreate) -> Consultation:
    advisor_ids = resolve_advisor_ids(payload.mode)
    c = Consultation(
        id=uuid4(),
        tenant_id=tenant_id,
        client_id=payload.client_id,
        created_by=user_id,
        title=payload.title,
        question=payload.question,
        situation=payload.situation,
        client_type=payload.client_type,
        domain=payload.domain,
        mode=ConsultationMode(payload.mode),
        attached_document_ids=payload.attached_document_ids,
        status=ConsultationStatus.QUEUED,
    )
    db.add(c)
    db.flush()
    for aid in advisor_ids:
        db.add(ConsultationAdvisor(id=uuid4(), consultation_id=c.id, tenant_id=tenant_id, advisor_id=aid, status=ConsultationStatus.QUEUED))
    db.commit()
    db.refresh(c)
    return c


def run_consultation(consultation_id: UUID, *, max_workers: int = 4) -> None:
    # Stage 1+2 (framing + grounding) need the main session.
    with SessionLocal() as db:
        c = db.get(Consultation, consultation_id)
        if c is None or c.status not in (ConsultationStatus.QUEUED, ConsultationStatus.FAILED):
            return
        c.status = ConsultationStatus.RUNNING
        c.started_at = datetime.now(timezone.utc)
        c.error = None
        db.commit()
        try:
            framing = _run_framing(c)
            grounding = _run_grounding(db, c, framing)
            c.framing = framing
            c.grounding = {"citations": grounding["citations"]}  # don't persist raw passages
            db.commit()
            brief = _build_brief(c, framing, grounding)
            cid = c.id
            tid = c.tenant_id
        except Exception as exc:  # noqa: BLE001
            log.exception("consultation_framing_failed", consultation_id=str(consultation_id))
            c.status = ConsultationStatus.FAILED
            c.error = f"Framing/grounding failed: {type(exc).__name__}: {exc}"[:2000]
            c.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        advisor_rows = db.execute(
            select(ConsultationAdvisor).where(ConsultationAdvisor.consultation_id == cid)
        ).scalars().all()
        adv_jobs = [(r.id, r.advisor_id) for r in advisor_rows if r.status in (ConsultationStatus.QUEUED, ConsultationStatus.FAILED)]

    # Stage 3: advisory panel (parallel, own sessions).
    outputs: list[dict] = []
    lock = threading.Lock()

    def _worker(row_id: UUID, advisor_id: str) -> None:
        with SessionLocal() as wdb:
            row = wdb.get(ConsultationAdvisor, row_id)
            if row is None:
                return
            row.status = ConsultationStatus.RUNNING
            row.started_at = datetime.now(timezone.utc)
            wdb.commit()
            try:
                raw = _run_one_advisor(advisor_id, brief)
                norm = _coerce(raw)
                row.position = norm["position"]
                row.confidence = norm["confidence"]
                row.key_points = norm["key_points"]
                row.citations = norm["citations"]
                row.caveats = norm["caveats"]
                row.extra = norm["extra"]
                row.raw_response = raw
                row.status = ConsultationStatus.DONE
                row.completed_at = datetime.now(timezone.utc)
                wdb.commit()
                with lock:
                    outputs.append({"advisor_id": advisor_id, **norm})
            except Exception as exc:  # noqa: BLE001
                log.exception("consultation_advisor_failed", advisor_id=advisor_id, consultation_id=str(cid))
                row.status = ConsultationStatus.FAILED
                row.error = f"{type(exc).__name__}: {exc}"[:2000]
                row.completed_at = datetime.now(timezone.utc)
                wdb.commit()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        concurrent.futures.wait([ex.submit(_worker, rid, aid) for rid, aid in adv_jobs])

    # Stage 4+5: synthesis + verification.
    with SessionLocal() as db:
        c = db.get(Consultation, cid)
        if c is None:
            return
        rows = db.execute(select(ConsultationAdvisor).where(ConsultationAdvisor.consultation_id == cid)).scalars().all()
        done = [{
            "advisor_id": r.advisor_id, "position": r.position, "confidence": r.confidence,
            "key_points": r.key_points or [], "citations": r.citations or [],
            "caveats": r.caveats or [], "extra": r.extra,
        } for r in rows if r.status == ConsultationStatus.DONE]
        if not done:
            c.status = ConsultationStatus.FAILED
            c.error = "All advisors failed — see per-advisor rows."
            c.completed_at = datetime.now(timezone.utc)
            db.commit()
            return
        try:
            framing = c.framing or {}
            grounding_full = {"citations": (c.grounding or {}).get("citations", []), "passages": []}
            opinion = _run_synthesis(c, framing, grounding_full, done)
            verification = _run_verification(opinion, grounding_full)
            c.final_opinion = opinion
            c.verification = verification
            conf = str(verification.get("confidence_level", "medium")).lower()
            c.confidence_level = ConsultationConfidence(conf) if conf in ("high", "medium", "low") else ConsultationConfidence.MEDIUM
            c.needs_human_review = verification.get("verdict") != "safe"
            c.status = ConsultationStatus.DONE
            c.completed_at = datetime.now(timezone.utc)
            db.commit()
            log.info("consultation_completed", consultation_id=str(cid), tenant_id=str(tid),
                     advisors_done=len(done), verdict=verification.get("verdict"))
        except Exception as exc:  # noqa: BLE001
            log.exception("consultation_synthesis_failed", consultation_id=str(cid))
            c.status = ConsultationStatus.FAILED
            c.error = f"Synthesis/verification failed: {type(exc).__name__}: {exc}"[:2000]
            c.completed_at = datetime.now(timezone.utc)
            db.commit()
