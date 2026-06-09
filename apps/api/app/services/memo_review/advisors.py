"""Advisor registry — one entry per virtual advisor (spec §5).

Each advisor has:
    * A fixed system prompt (Arabic + English) tuned to its niche.
    * A JSON-schema response shape conforming to the spec §7 fixed template
      (assessment / observations / risk_points / recommendations / impact_level
      + optional `extra` for advisor-specific fields).

Phase 1 ships 4 advisors (per spec §13). Phase 2/3 entries are listed in
the mode tuples so the registry doesn't need re-shuffling later — only the
prompts and schemas get filled in when those phases ship.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdvisorSpec:
    """One virtual advisor (spec §5)."""

    id: str
    name_en: str
    name_ar: str
    main_question_en: str
    main_question_ar: str
    system_prompt: str
    schema: dict
    """JSON Schema for structured output (spec §7 fixed template)."""


# ---------------------------------------------------------------------------
# Shared schema fragment (spec §7).
# Every advisor returns this shape so the UI can render every card uniformly.
# `extra` is optional — advisors with specialized fields (compensation,
# requests) add structured keys there without breaking the common contract.
# ---------------------------------------------------------------------------

BASE_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "required": ["assessment", "observations", "risk_points", "recommendations", "impact_level"],
    "properties": {
        "assessment": {
            "type": "string",
            "enum": ["strong", "medium", "weak"],
            "description": "Overall strength of the angle this advisor reviewed.",
        },
        "observations": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {"type": "string"},
            "description": "3–5 concise key observations (spec §7).",
        },
        "risk_points": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {"type": "string"},
            "description": "1–3 risk points (spec §7).",
        },
        "recommendations": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {"type": "string"},
            "description": "2–4 practical recommendations (spec §7).",
        },
        "impact_level": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "How impactful these findings are to the memo's strength.",
        },
        "extra": {
            "type": "object",
            "description": "Advisor-specific fields (e.g. proposed legal characterization).",
        },
    },
}


# ---------------------------------------------------------------------------
# Shared system-prompt preamble — applied to every advisor.
# ---------------------------------------------------------------------------

PREAMBLE = """\
You are a senior Saudi-law expert acting as a specialized advisor on a
multi-advisor memo review panel. You will read a case file (facts, claims,
the current draft memo, and optional supporting documents) and produce
critical, structured feedback ONLY from your assigned angle.

HARD RULES (do not violate):
  1. Stay in your lane — do not comment on angles outside your specialty.
  2. Be specific and concrete — every observation must reference a part of
     the memo or a part of the facts. Avoid generic advice.
  3. Cite Saudi law where relevant. If you cite a statute, name it precisely
     (e.g. "نظام المعاملات المدنية مادة 84" not "the civil code").
  4. Do NOT invent facts, parties, dates, or amounts that are not in the
     case file. Mark anything uncertain with "needs human verification".
  5. Output language: match the language of the memo (if memo is in Arabic,
     reply in Arabic; if English, reply in English; if mixed, reply in Arabic).
  6. Output STRICTLY follows the JSON schema you were given — no prose
     outside it, no markdown, no surrounding commentary.

Your output will be merged with 3–9 other independent advisors by a final
review manager, so keep it tight: 3–5 observations, 1–3 risk points,
2–4 recommendations. Quality over volume.
"""


def _prompt(specific: str) -> str:
    return PREAMBLE + "\n\nYOUR SPECIALTY:\n" + specific.strip() + "\n"


# ---------------------------------------------------------------------------
# Phase 1 advisors (spec §13)
# ---------------------------------------------------------------------------

CHARACTERIZATION = AdvisorSpec(
    id="characterization",
    name_en="Legal Characterization Advisor",
    name_ar="مستشار التكييف القانوني",
    main_question_en="Has the case been legally characterized correctly?",
    main_question_ar="هل تم تكييف القضية قانونياً بالشكل الصحيح؟",
    system_prompt=_prompt(
        """
Legal Characterization Advisor (مستشار التكييف القانوني).

Your job is to verify that the case has been correctly described and
legally characterized. Focus on:
  * The TYPE of lawsuit (نوع الدعوى) — is it civil, commercial, labor,
    administrative, family, etc.?
  * Whether the legal description matches the underlying right being
    asserted (e.g. is this an action for damages, specific performance,
    rescission, declaratory relief?).
  * The general statutory basis — is the right being asserted founded in
    the Civil Transactions Law, Commercial Law, Personal Status Law,
    Labor Law, an administrative regulation, etc.?
  * Suitability of the requests/claims to the nature of the right.

Your `extra` field should include:
  {
    "proposed_characterization": "<short label of the correct type>",
    "current_characterization_correct": <true|false|"partial">,
    "most_appropriate_statutory_basis": "<the primary statute and article>"
  }
"""
    ),
    schema={
        **BASE_OUTPUT_SCHEMA,
        "properties": {
            **BASE_OUTPUT_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": [
                    "proposed_characterization",
                    "current_characterization_correct",
                    "most_appropriate_statutory_basis",
                ],
                "properties": {
                    "proposed_characterization": {"type": "string"},
                    "current_characterization_correct": {"type": "string"},
                    "most_appropriate_statutory_basis": {"type": "string"},
                },
            },
        },
    },
)


EVIDENCE = AdvisorSpec(
    id="evidence",
    name_en="Evidence and Proof Advisor",
    name_ar="مستشار الأدلة والإثبات",
    main_question_en="Does the evidentiary file support the memo sufficiently?",
    main_question_ar="هل ملف الأدلة يدعم المذكرة بشكل كاف؟",
    system_prompt=_prompt(
        """
Evidence and Proof Advisor (مستشار الأدلة والإثبات).

Analyze the evidence and determine its sufficiency and weaknesses. Focus on:
  * What evidence is available (named in facts / attached documents).
  * What evidence is missing for each claim asserted in the memo.
  * Burden of proof — who must prove what, under Saudi Evidence Law
    (نظام الإثبات), and is that burden plausibly met?
  * Strength of each cited document (official document, signed contract,
    witness statement, expert report, party admission, etc.).
  * The relationship of each piece of evidence to the specific claim.

Your `extra` field should include:
  {
    "strong_evidence":    ["<short label of each piece of strong evidence>"],
    "weak_evidence":      ["<short label of each piece of weak evidence>"],
    "missing_evidence":   ["<what's missing and why it matters>"],
    "completion_recommendation": "<single sentence: how to plug the gap>"
  }
"""
    ),
    schema={
        **BASE_OUTPUT_SCHEMA,
        "properties": {
            **BASE_OUTPUT_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": ["strong_evidence", "weak_evidence", "missing_evidence", "completion_recommendation"],
                "properties": {
                    "strong_evidence": {"type": "array", "items": {"type": "string"}},
                    "weak_evidence": {"type": "array", "items": {"type": "string"}},
                    "missing_evidence": {"type": "array", "items": {"type": "string"}},
                    "completion_recommendation": {"type": "string"},
                },
            },
        },
    },
)


PROCEDURES = AdvisorSpec(
    id="procedures",
    name_en="Procedures and Formal Defenses Advisor",
    name_ar="مستشار الإجراءات والدفوع الشكلية",
    main_question_en="Is there a formal gap or an impactful procedural defense?",
    main_question_ar="هل هناك خلل شكلي أو دفع إجرائي مؤثر؟",
    system_prompt=_prompt(
        """
Procedures and Formal Defenses Advisor (مستشار الإجراءات والدفوع الشكلية).

Examine the procedural and formal aspects of the case and memo. Focus on:
  * Jurisdiction (الاختصاص) — both subject-matter (نوعي) and territorial
    (مكاني) under نظام المرافعات الشرعية / Commercial Court / Labor Court /
    Board of Grievances jurisdiction rules.
  * Standing / capacity (الصفة) — is the plaintiff the right party to sue?
    Is the defendant correctly named?
  * Interest (المصلحة) — is the plaintiff's interest direct, lawful, and
    currently subsisting?
  * Formal admissibility (القبول الشكلي) — are time limits, prior-notice
    requirements, mediation prerequisites, payment of court fees, etc.
    all satisfied?
  * Any latent formal defense the opponent could raise (defective service,
    expired statute of limitations, missing power of attorney, etc.).

Your `extra` field should include:
  {
    "potential_formal_defenses": ["<defense> — <effect if accepted>"],
    "procedural_defects_present": <true|false>,
    "ordering_recommendation": "<which defense to raise / address first>"
  }
"""
    ),
    schema={
        **BASE_OUTPUT_SCHEMA,
        "properties": {
            **BASE_OUTPUT_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": ["potential_formal_defenses", "procedural_defects_present", "ordering_recommendation"],
                "properties": {
                    "potential_formal_defenses": {"type": "array", "items": {"type": "string"}},
                    "procedural_defects_present": {"type": "string"},
                    "ordering_recommendation": {"type": "string"},
                },
            },
        },
    },
)


DRAFTING = AdvisorSpec(
    id="drafting",
    name_en="Legal Drafting and Language Advisor",
    name_ar="مستشار الصياغة القانونية واللغة",
    main_question_en="Is the memo written with strong, persuasive legal drafting?",
    main_question_ar="هل المذكرة مكتوبة بصياغة قانونية قوية ومقنعة؟",
    system_prompt=_prompt(
        """
Legal Drafting and Language Advisor (مستشار الصياغة القانونية واللغة).

Improve the quality of the memo in terms of language, logic, and cohesion.
You are NOT rewriting it from scratch — you are critiquing and proposing
specific surgical improvements. Focus on:
  * Judicial style (الأسلوب القضائي) — appropriate register, formality,
    third-person voice, restrained tone.
  * Cohesion (الترابط) — does each paragraph flow from the previous one?
  * Repetition — is the same point made twice or three times?
  * Paragraph clarity — are sentences too long, too tangled, or unclear?
  * Strength of transitions between ideas, between facts and law,
    between argument and conclusion.

Your `extra` field should include:
  {
    "weak_sentences": [
      {"original": "<quote>", "suggested_rewrite": "<better version>"}
    ],
    "repetition_points": ["<short label of each repeated idea>"],
    "style_grade": "<excellent|good|acceptable|needs_work|poor>"
  }
"""
    ),
    schema={
        **BASE_OUTPUT_SCHEMA,
        "properties": {
            **BASE_OUTPUT_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": ["weak_sentences", "repetition_points", "style_grade"],
                "properties": {
                    "weak_sentences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["original", "suggested_rewrite"],
                            "properties": {
                                "original": {"type": "string"},
                                "suggested_rewrite": {"type": "string"},
                            },
                        },
                    },
                    "repetition_points": {"type": "array", "items": {"type": "string"}},
                    "style_grade": {"type": "string"},
                },
            },
        },
    },
)


# ---------------------------------------------------------------------------
# Phase 2 & 3 advisors (spec §13) — placeholders pending those phases.
# Stub specs keep them resolvable but they raise NotImplementedError at run
# time so a typo doesn't quietly trigger a non-existent advisor.
# ---------------------------------------------------------------------------


def _stub(id: str, name_en: str, name_ar: str, phase: int) -> AdvisorSpec:
    """Placeholder advisor for Phase 2/3 — not callable yet."""
    return AdvisorSpec(
        id=id,
        name_en=name_en,
        name_ar=name_ar,
        main_question_en=f"[Phase {phase} advisor — not yet implemented]",
        main_question_ar=f"[مستشار من المرحلة {phase} — لم يُفعّل بعد]",
        system_prompt=f"_PHASE_{phase}_STUB",
        schema=BASE_OUTPUT_SCHEMA,
    )


STATUTES = _stub("statutes", "Statutes and Regulatory Compliance Advisor", "مستشار الأنظمة والامتثال التشريعي", 2)
FACTS = _stub("facts", "Facts and Chronology Advisor", "مستشار الوقائع والتسلسل الزمني", 2)
OPPONENT = _stub("opponent", "Opponent and Counter-Attack Advisor", "مستشار الخصم والهجوم المضاد", 2)
COMPENSATION = _stub("compensation", "Compensation and Damages Advisor", "مستشار التعويضات والأضرار", 3)
REQUESTS = _stub("requests", "Requests and Practical Outcome Advisor", "مستشار الطلبات والمآل العملي", 3)
RISKS = _stub("risks", "Risks and Alerts Advisor", "مستشار المخاطر والتنبيهات", 3)


# ---------------------------------------------------------------------------
# Registry + mode mappings
# ---------------------------------------------------------------------------

ADVISORS: dict[str, AdvisorSpec] = {
    a.id: a
    for a in (
        CHARACTERIZATION,
        EVIDENCE,
        PROCEDURES,
        DRAFTING,
        STATUTES,
        FACTS,
        OPPONENT,
        COMPENSATION,
        REQUESTS,
        RISKS,
    )
}

# Phase 1 ships and is callable today.
PHASE_1_ADVISORS: tuple[str, ...] = ("characterization", "evidence", "procedures", "drafting")
PHASE_2_ADVISORS: tuple[str, ...] = ("statutes", "facts", "opponent")
PHASE_3_ADVISORS: tuple[str, ...] = ("compensation", "requests", "risks")

# Mode mappings (spec §9).
#   standard = 7 core advisors (Phase 1 + Phase 2)
#   deep     = all 10
#   custom   = whatever the user selects (validated against ADVISORS)
STANDARD_MODE_ADVISORS: tuple[str, ...] = PHASE_1_ADVISORS + PHASE_2_ADVISORS
DEEP_MODE_ADVISORS: tuple[str, ...] = PHASE_1_ADVISORS + PHASE_2_ADVISORS + PHASE_3_ADVISORS


def resolve_advisor_ids(mode: str, selected: list[str] | None) -> list[str]:
    """Resolve the final list of advisors to run for a review.

    Filters out any advisor whose system_prompt is still a stub — so a
    "standard" or "deep" run today only actually fires the Phase-1 advisors.
    Later phases plug in by replacing the stub specs above.
    """
    if mode == "custom":
        if not selected:
            raise ValueError("Custom mode requires `selected_advisors`.")
        unknown = [a for a in selected if a not in ADVISORS]
        if unknown:
            raise ValueError(f"Unknown advisor(s): {unknown}")
        wanted = selected
    elif mode == "standard":
        wanted = list(STANDARD_MODE_ADVISORS)
    else:  # deep (default)
        wanted = list(DEEP_MODE_ADVISORS)

    # Drop stub advisors — return only those whose prompt is real today.
    return [a for a in wanted if not ADVISORS[a].system_prompt.startswith("_PHASE_")]
