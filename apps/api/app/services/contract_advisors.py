"""Multi-advisor contract review panel.

Same idea as the case-analysis / consultation panels, tuned for contracts:
several specialized advisors each read the SAME contract text from a distinct
angle (risk, Saudi-law compliance, fairness/balance, missing clauses, and —
in deep mode — termination/dispute & drafting clarity). A synthesizer merges
their findings into one prioritized review (the existing ContractReviewResponse
shape) plus an overall party-favorability read.

Runs synchronously: advisors fan out in parallel threads (no DB needed — they
only need the text + the LLM), so wall-clock ≈ slowest advisor + synthesis.
"""
from __future__ import annotations

import concurrent.futures
import json

from app.core.logging import get_logger
from app.services.llm import get_llm_provider

log = get_logger(__name__)


# ── advisor output schema (shared) ─────────────────────────────────────
_ADVISOR_SCHEMA: dict = {
    "type": "object",
    "required": ["assessment", "favors", "findings"],
    "properties": {
        "assessment": {"type": "string", "description": "One-paragraph read from this angle."},
        "favors": {
            "type": "string",
            "enum": ["client", "counterparty", "balanced", "na"],
            "description": "Which side this angle's issues tend to favor.",
        },
        "findings": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "required": ["severity", "category", "title", "description"],
                "properties": {
                    "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "clause_excerpt": {"type": "string"},
                },
            },
        },
    },
}


def _preamble(locale: str) -> str:
    lang = "Arabic" if locale == "ar" else "the contract's language"
    return f"""\
You are a senior Saudi-law contracts specialist on a multi-advisor contract
review panel. You review the SAME contract from YOUR assigned angle only.

HARD RULES:
  1. Stay in your lane.
  2. Quote the offending clause verbatim in `clause_excerpt` when you flag it.
  3. Ground compliance points in Saudi law; name statutes precisely
     (e.g. نظام المعاملات المدنية مادة 178). If unsure an article exists,
     say so in the description rather than inventing a number.
  4. Reply in {lang}.
  5. Output STRICTLY the given JSON schema — no prose, no markdown.

`favors`: from the perspective of OUR CLIENT (the party seeking this review),
does your angle reveal terms that favor the client, the counterparty, or are
balanced? Use "na" if not applicable to your angle.
"""


# ── advisor registry ───────────────────────────────────────────────────
_ADVISORS: dict[str, dict[str, str]] = {
    "risk": {
        "name_en": "Risk & Liability Advisor",
        "name_ar": "مستشار المخاطر والمسؤولية",
        "focus": (
            "Liability exposure: unlimited/uncapped liability, one-sided indemnities, "
            "penalties & liquidated damages, warranties/guarantees, insurance gaps, "
            "and any clause that shifts disproportionate financial risk onto our client."
        ),
    },
    "compliance": {
        "name_en": "Saudi-Law Compliance Advisor",
        "name_ar": "مستشار الامتثال النظامي",
        "focus": (
            "Compliance with Saudi law. Flag void/unenforceable clauses under the Civil "
            "Transactions Law (نظام المعاملات المدنية), Labor Law, Commercial Courts Law, "
            "etc.; usurious/riba terms; clauses contrary to public order (النظام العام); "
            "and anything a Saudi court would strike or refuse to enforce."
        ),
    },
    "balance": {
        "name_en": "Balance & Fairness Advisor",
        "name_ar": "مستشار التوازن والإنصاف",
        "focus": (
            "Overall fairness. For each major obligation/right, note which party it favors. "
            "Surface one-sided termination rights, asymmetric notice periods, unilateral "
            "amendment rights, and lopsided dispute/forum clauses."
        ),
    },
    "missing": {
        "name_en": "Missing Clauses Advisor",
        "name_ar": "مستشار البنود الناقصة",
        "focus": (
            "Essential clauses that are ABSENT and should be added: force majeure, "
            "confidentiality, dispute resolution & governing law, termination & notice, "
            "limitation of liability, assignment, entire-agreement, payment terms, IP "
            "ownership — whatever this contract type needs but lacks."
        ),
    },
    "termination": {
        "name_en": "Termination & Dispute Advisor",
        "name_ar": "مستشار الإنهاء والمنازعات",
        "focus": (
            "Termination rights & triggers, notice/cure periods, post-termination "
            "obligations, dispute-resolution mechanism, governing law, jurisdiction/"
            "arbitration seat, and enforceability of the forum choice in Saudi Arabia."
        ),
    },
    "clarity": {
        "name_en": "Drafting & Clarity Advisor",
        "name_ar": "مستشار الصياغة والوضوح",
        "focus": (
            "Drafting quality: ambiguous or undefined terms, internal contradictions, "
            "inconsistent defined terms, vague obligations ('reasonable efforts' without "
            "a standard), and cross-reference errors that create interpretation risk."
        ),
    },
}

STANDARD_MODE = ("risk", "compliance", "balance", "missing")
DEEP_MODE = STANDARD_MODE + ("termination", "clarity")


def advisor_label(advisor_id: str, locale: str) -> str:
    a = _ADVISORS.get(advisor_id, {})
    return a.get("name_ar" if locale == "ar" else "name_en", advisor_id)


def _run_one(advisor_id: str, contract_text: str, locale: str) -> dict:
    spec = _ADVISORS[advisor_id]
    system = _preamble(locale) + "\n\nYOUR ANGLE:\n" + spec["focus"]
    user = ("نص العقد:\n" if locale == "ar" else "Contract text:\n") + contract_text
    provider = get_llm_provider()
    raw = provider.structured(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        _ADVISOR_SCHEMA,
        temperature=0.15,
    )
    return raw


# ── synthesizer ─────────────────────────────────────────────────────────
_SYNTH_SCHEMA: dict = {
    "type": "object",
    "required": ["summary", "findings", "suggestions", "missing_clauses", "risk_score", "party_favorability"],
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["severity", "category", "title", "description"],
                "properties": {
                    "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical"]},
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "clause_excerpt": {"type": "string"},
                },
            },
        },
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "rationale", "suggested_clause"],
                "properties": {
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "suggested_clause": {"type": "string"},
                },
            },
        },
        "missing_clauses": {"type": "array", "items": {"type": "string"}},
        "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "party_favorability": {
            "type": "string",
            "description": "Overall: does the contract favor our client, the counterparty, or is it balanced? One sentence.",
        },
    },
}


def _synth_system(locale: str) -> str:
    lang = "Arabic" if locale == "ar" else "the contract's language"
    return f"""\
You are the lead reviewer synthesizing a contract review from an advisory panel
(risk, compliance, fairness, missing clauses, and possibly termination & drafting).
Merge their findings: remove duplicates, keep the highest severity when two
advisors flag the same clause, and prioritize.

Produce:
  - summary: 2-4 sentences — what this contract is and the headline concerns.
  - findings: the consolidated, de-duplicated issues (severity-ordered).
  - suggestions: concrete redline proposals (a better clause to add/replace).
  - missing_clauses: essential clauses that are absent.
  - risk_score: 0-100 (0 = clean, 100 = do-not-sign).
  - party_favorability: one sentence on which side the contract favors overall.

Reply in {lang}. Output STRICTLY the given JSON schema.
"""


def panel_advisor_ids(mode: str) -> list[str]:
    return list(DEEP_MODE if mode == "deep" else STANDARD_MODE)


def run_panel(
    contract_text: str,
    *,
    locale: str,
    mode: str = "standard",
    max_workers: int = 4,
    on_advisor_done=None,
    on_synthesis_start=None,
) -> tuple[list[dict], dict]:
    """Run the advisor panel + synthesizer.

    Returns (advisor_opinions, synthesis_dict). advisor_opinions is a list of
    { advisor_id, name, assessment, favors, findings }.

    `on_advisor_done(advisor_id, result_dict)` fires as each advisor finishes
    (used to stream progress to a job row). `on_synthesis_start()` fires once
    all advisors are done and the merge begins.
    """
    advisor_ids = panel_advisor_ids(mode)

    results: dict[str, dict] = {}

    def _worker(aid: str) -> None:
        try:
            results[aid] = _run_one(aid, contract_text, locale)
        except Exception as exc:  # noqa: BLE001
            log.warning("contract_advisor_failed", advisor_id=aid, error=str(exc))
            results[aid] = {"assessment": f"(failed: {exc})", "favors": "na", "findings": []}
        if on_advisor_done is not None:
            try:
                on_advisor_done(aid, results[aid])
            except Exception:  # noqa: BLE001
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        concurrent.futures.wait([ex.submit(_worker, aid) for aid in advisor_ids])

    if on_synthesis_start is not None:
        try:
            on_synthesis_start()
        except Exception:  # noqa: BLE001
            pass

    advisor_opinions: list[dict] = []
    for aid in advisor_ids:
        r = results.get(aid, {})
        advisor_opinions.append({
            "advisor_id": aid,
            "name": advisor_label(aid, locale),
            "assessment": r.get("assessment", ""),
            "favors": r.get("favors", "na"),
            "findings": r.get("findings", []),
        })

    # Synthesize.
    panel_block = "\n\n".join(
        f"=== {advisor_label(aid, locale)} (favors: {results.get(aid, {}).get('favors', 'na')}) ===\n"
        + json.dumps(results.get(aid, {}).get("findings", []), ensure_ascii=False, indent=2)
        for aid in advisor_ids
    )
    provider = get_llm_provider()
    synthesis = provider.structured(
        [
            {"role": "system", "content": _synth_system(locale)},
            {"role": "user", "content": "ADVISOR FINDINGS:\n\n" + panel_block},
        ],
        _SYNTH_SCHEMA,
        temperature=0.1,
    )
    return advisor_opinions, synthesis
