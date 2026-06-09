"""Legal Opinion Engine — advisory panel + synthesizer + verification gate.

Public API:
    * start_consultation(...) — create the row + queued advisor rows.
    * run_consultation(id)    — execute end-to-end (sync; API + Celery safe).
    * ADVISORS, STANDARD_MODE_ADVISORS, DEEP_MODE_ADVISORS
"""
from app.services.consultation.advisors import (
    ADVISORS,
    DEEP_MODE_ADVISORS,
    STANDARD_MODE_ADVISORS,
    ConsultationAdvisorSpec,
    resolve_advisor_ids,
)
from app.services.consultation.orchestrator import run_consultation, start_consultation

__all__ = [
    "ADVISORS",
    "ConsultationAdvisorSpec",
    "DEEP_MODE_ADVISORS",
    "STANDARD_MODE_ADVISORS",
    "resolve_advisor_ids",
    "run_consultation",
    "start_consultation",
]
