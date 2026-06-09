from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.subscription import PlanTier, SubscriptionStatus


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tier: PlanTier
    name_en: str
    name_ar: str
    price_monthly_sar: int
    price_monthly_usd: int
    monthly_messages_limit: int
    monthly_documents_limit: int
    monthly_contracts_limit: int
    seats_limit: int
    is_active: bool


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    provider: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_ends_at: datetime | None


class CheckoutRequest(BaseModel):
    plan_tier: PlanTier
    provider: Literal["stripe", "moyasar"] = "stripe"
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str
    provider_session_id: str


class ChangePlanRequest(BaseModel):
    """Switch the tenant from the current plan to another tier.

    Behaviour:
      - First time on a paid plan → routed through full checkout.
      - Already subscribed → goes through provider's portal/upgrade flow
        (returns the same checkout_url shape so the frontend treats both the
        same).
    """

    plan_tier: PlanTier
    provider: Literal["stripe", "moyasar"] = "stripe"
    success_url: str
    cancel_url: str


class UsageMetric(BaseModel):
    """One row in the usage dashboard."""

    kind: str  # "message", "document_upload", "contract_review", "seats"
    used: int
    limit: int  # 0 means unlimited
    remaining: int  # max(limit - used, 0); always 0 when unlimited
    percentage: float  # 0.0 - 1.0; 0.0 when unlimited


class UsageRead(BaseModel):
    """Period usage for the dashboard's "current plan" widget."""

    plan_tier: PlanTier | None = None
    plan_name_en: str | None = None
    plan_name_ar: str | None = None
    status: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    metrics: list[UsageMetric]
