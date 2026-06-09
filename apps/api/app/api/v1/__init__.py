"""v1 API routers wired together for inclusion in `main.py`."""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    cases,
    chat,
    clients,
    compliance,
    consultation,
    contracts,
    crm,
    documents,
    drafting,
    invoices,
    memo_review,
    onboarding,
    plans,
    subdomains,
    subscriptions,
    team,
    templates,
    tenants,
    webhooks,
    whatsapp,
)

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(drafting.router, prefix="/drafting", tags=["drafting"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_router.include_router(plans.router, prefix="/plans", tags=["billing"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["billing"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["billing"])
api_router.include_router(team.router, prefix="/team", tags=["team"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(subdomains.router, prefix="/subdomains", tags=["tenants"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
api_router.include_router(compliance.router, prefix="/compliance", tags=["compliance"])
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

# Multi-advisor memo review + Najiz final-review gate.
api_router.include_router(memo_review.memo_reviews_router, prefix="/memo-reviews", tags=["memo-review"])
api_router.include_router(memo_review.final_reviews_router, prefix="/final-reviews", tags=["memo-review"])

# Legal Opinion Engine (consultations).
api_router.include_router(consultation.router, prefix="/consultations", tags=["consultation"])

# CRM workspace routers — split by entity for cleaner OpenAPI groups.
api_router.include_router(crm.tasks_router, prefix="/tasks", tags=["crm"])
api_router.include_router(crm.hearings_router, prefix="/hearings", tags=["crm"])
api_router.include_router(crm.time_entries_router, prefix="/time-entries", tags=["crm"])
api_router.include_router(crm.notes_router, prefix="/case-notes", tags=["crm"])
api_router.include_router(crm.contacts_router, prefix="/contacts", tags=["crm"])
api_router.include_router(crm.activities_router, prefix="/activities", tags=["crm"])
api_router.include_router(crm.dashboard_router, prefix="/dashboard", tags=["crm"])

# Webhooks are mounted at /webhooks (not /v1/webhooks) so providers can use a
# stable URL across API versions. See main.py.
