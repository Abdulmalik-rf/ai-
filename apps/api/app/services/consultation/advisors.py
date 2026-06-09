"""Consultation advisory-panel registry (spec: Legal Opinion Engine).

Each advisor answers the SAME client question from a distinct advisory angle,
independently (no advisor sees another's output). The synthesizer merges them.

Standard mode = 4 advisors (statutory / risk / options / procedural).
Deep mode     = + devil's advocate.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsultationAdvisorSpec:
    id: str
    name_en: str
    name_ar: str
    system_prompt: str
    schema: dict


# ── Shared output shape ────────────────────────────────────────────────
BASE_SCHEMA: dict = {
    "type": "object",
    "required": ["position", "confidence", "key_points", "citations", "caveats"],
    "properties": {
        "position": {
            "type": "string",
            "description": "One-paragraph stance on the question, from this angle.",
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "key_points": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {"type": "string"},
        },
        "citations": {
            "type": "array",
            "description": "Saudi statutes/articles relied on.",
            "items": {
                "type": "object",
                "required": ["statute", "relevance"],
                "properties": {
                    "statute": {"type": "string", "description": "e.g. نظام المعاملات المدنية"},
                    "article": {"type": "string", "description": "e.g. مادة 84 (if known)"},
                    "relevance": {"type": "string"},
                },
            },
        },
        "caveats": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string"},
            "description": "Limits, unknowns, or 'needs human verification' notes.",
        },
        "extra": {"type": "object", "description": "Advisor-specific structured fields."},
    },
}


PREAMBLE = """\
You are a senior Saudi-law advisor on a multi-advisor legal-CONSULTATION panel.
You are NOT critiquing a court pleading — you are answering a client's
forward-looking question ("can I / should I / what's my exposure") from your
assigned angle only.

HARD RULES:
  1. Stay in your lane — only your assigned angle.
  2. Ground every legal claim in Saudi law. Name statutes precisely
     (e.g. "نظام العمل مادة 77"). If you are unsure an article exists or
     applies, mark it in `caveats` as "needs human verification" — never
     invent an article number, decree number, or case citation.
  3. Use ONLY the facts in the client's situation. If a material fact is
     missing, say so in `caveats` rather than assuming it.
  4. Output language: match the client's question (Arabic question → Arabic
     answer; English → English; mixed → Arabic).
  5. Output STRICTLY the given JSON schema — no prose, no markdown.

Your answer is one of 4–5 independent advisor inputs to a synthesizer; keep
it tight and concrete.
"""


def _p(specific: str) -> str:
    return PREAMBLE + "\n\nYOUR ANGLE:\n" + specific.strip() + "\n"


STATUTORY = ConsultationAdvisorSpec(
    id="statutory",
    name_en="Statutory Analysis Advisor",
    name_ar="مستشار التحليل النظامي",
    system_prompt=_p(
        """
Statutory Analysis Advisor (مستشار التحليل النظامي).
Answer strictly on what Saudi law literally permits, requires, or prohibits
for this situation. Identify the governing statute(s) and the specific
articles. State plainly whether the contemplated action/right is:
permitted, prohibited, permitted-with-conditions, or unregulated (silent).
`extra`: { "legal_status": "permitted|prohibited|conditional|unregulated",
           "governing_statutes": ["..."] }
"""
    ),
    schema={
        **BASE_SCHEMA,
        "properties": {
            **BASE_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": ["legal_status", "governing_statutes"],
                "properties": {
                    "legal_status": {"type": "string"},
                    "governing_statutes": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
)


RISK = ConsultationAdvisorSpec(
    id="risk",
    name_en="Risk & Liability Advisor",
    name_ar="مستشار المخاطر والمسؤولية",
    system_prompt=_p(
        """
Risk & Liability Advisor (مستشار المخاطر والمسؤولية).
Identify what could go wrong: civil liability, penalties/fines, criminal
exposure, regulatory sanction, contractual breach consequences, reputational
or enforcement risk. Rate the overall exposure.
`extra`: { "exposure_level": "high|medium|low",
           "worst_case": "<short>" }
"""
    ),
    schema={
        **BASE_SCHEMA,
        "properties": {
            **BASE_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": ["exposure_level", "worst_case"],
                "properties": {
                    "exposure_level": {"type": "string"},
                    "worst_case": {"type": "string"},
                },
            },
        },
    },
)


OPTIONS = ConsultationAdvisorSpec(
    id="options",
    name_en="Options & Alternatives Advisor",
    name_ar="مستشار الخيارات والبدائل",
    system_prompt=_p(
        """
Options & Alternatives Advisor (مستشار الخيارات والبدائل).
Lay out the lawful paths available to the client to achieve their goal (or
mitigate the problem), each with trade-offs. Rank them. If the best option
isn't the obvious one, say why.
`extra`: { "options": [ {"option":"...","pros":["..."],"cons":["..."],"rank":1} ] }
"""
    ),
    schema={
        **BASE_SCHEMA,
        "properties": {
            **BASE_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": ["options"],
                "properties": {
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["option", "pros", "cons", "rank"],
                            "properties": {
                                "option": {"type": "string"},
                                "pros": {"type": "array", "items": {"type": "string"}},
                                "cons": {"type": "array", "items": {"type": "string"}},
                                "rank": {"type": "integer"},
                            },
                        },
                    },
                },
            },
        },
    },
)


PROCEDURAL = ConsultationAdvisorSpec(
    id="procedural",
    name_en="Procedural & Practical Advisor",
    name_ar="مستشار الإجراءات والتطبيق العملي",
    system_prompt=_p(
        """
Procedural & Practical Advisor (مستشار الإجراءات والتطبيق العملي).
Give the concrete steps to act on this: which authority/portal (Najiz, MoJ,
ZATCA, MHRSD, MoC, Board of Grievances, etc.), what documents are needed,
expected timelines, fees, and the order of operations.
`extra`: { "steps": ["..."], "authority": "...", "documents_needed": ["..."] }
"""
    ),
    schema={
        **BASE_SCHEMA,
        "properties": {
            **BASE_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": ["steps", "authority", "documents_needed"],
                "properties": {
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "authority": {"type": "string"},
                    "documents_needed": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
)


DEVILS_ADVOCATE = ConsultationAdvisorSpec(
    id="devils_advocate",
    name_en="Devil's Advocate Advisor",
    name_ar="مستشار الرأي المعارض",
    system_prompt=_p(
        """
Devil's Advocate Advisor (مستشار الرأي المعارض).
Argue against the client's desired outcome. How would a regulator, judge, or
counterparty challenge it? What weaknesses, counter-arguments, or unfavourable
interpretations exist? Surface the strongest case AGAINST proceeding.
`extra`: { "strongest_counterargument": "...", "rebuttal_difficulty": "high|medium|low" }
"""
    ),
    schema={
        **BASE_SCHEMA,
        "properties": {
            **BASE_SCHEMA["properties"],
            "extra": {
                "type": "object",
                "required": ["strongest_counterargument", "rebuttal_difficulty"],
                "properties": {
                    "strongest_counterargument": {"type": "string"},
                    "rebuttal_difficulty": {"type": "string"},
                },
            },
        },
    },
)


ADVISORS: dict[str, ConsultationAdvisorSpec] = {
    a.id: a for a in (STATUTORY, RISK, OPTIONS, PROCEDURAL, DEVILS_ADVOCATE)
}

STANDARD_MODE_ADVISORS: tuple[str, ...] = ("statutory", "risk", "options", "procedural")
DEEP_MODE_ADVISORS: tuple[str, ...] = STANDARD_MODE_ADVISORS + ("devils_advocate",)


def resolve_advisor_ids(mode: str) -> list[str]:
    return list(DEEP_MODE_ADVISORS if mode == "deep" else STANDARD_MODE_ADVISORS)
