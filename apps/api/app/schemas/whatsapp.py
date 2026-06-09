from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.case import LegalDomain
from app.models.whatsapp import WhatsAppSessionStatus


class SessionStatusRead(BaseModel):
    """What the dashboard polls. `qr` is non-null only while pairing."""

    model_config = ConfigDict(from_attributes=True)

    status: WhatsAppSessionStatus
    qr: str | None = None
    phone_number: str | None = None
    display_name: str | None = None
    last_disconnect_reason: str | None = None
    last_qr_at: datetime | None = None
    last_connected_at: datetime | None = None


class AllowedSenderCreate(BaseModel):
    wa_phone: str = Field(min_length=4, max_length=32)
    label: str | None = Field(default=None, max_length=200)


class AllowedSenderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wa_phone: str
    label: str | None = None
    created_at: datetime


# ----- Bridge → FastAPI inbound webhook --------------------------------------


class BridgeInboundMessage(BaseModel):
    """Posted by the bridge whenever a tenant's socket receives a message."""

    tenant_id: UUID
    from_phone: str
    text: str = ""
    image_url: str | None = None
    image_data_url: str | None = None
    timestamp: int | None = None  # epoch seconds


class BridgeInboundReply(BaseModel):
    """What FastAPI returns to the bridge after running the agent."""

    text: str
    escalated: bool = False


# ----- Bridge → FastAPI session-update webhook -------------------------------


class BridgeSessionUpdate(BaseModel):
    """Pushed by the bridge whenever the connection state changes.

    Status lifecycle: pairing (qr present) → connected (phone_number set) →
    disconnected | logged_out | error.
    """

    tenant_id: UUID
    status: WhatsAppSessionStatus
    qr: str | None = None
    phone_number: str | None = None
    display_name: str | None = None
    last_disconnect_reason: str | None = None


# ----- Agent profile (per-tenant tuning) -------------------------------------


class AgentProfileRead(BaseModel):
    """The current tuning settings for a tenant's WhatsApp intake agent.

    Every field is optional — anything blank defers to the baseline prompt
    in app.services.agent. The dashboard renders this as a form.
    """

    model_config = ConfigDict(from_attributes=True)

    firm_display_name: str | None = None
    welcome_message_ar: str | None = None
    welcome_message_en: str | None = None
    firm_specialties: str | None = None
    consultation_offer: str | None = None
    tone_guidelines: str | None = None
    custom_instructions: str | None = None
    timezone: str = "Asia/Riyadh"
    enabled_domains: list[str] = Field(default_factory=list)
    is_enabled: bool = True
    updated_at: datetime | None = None


class AgentProfileUpdate(BaseModel):
    """Partial update for the tuning fields. Send only what changed."""

    firm_display_name: str | None = Field(default=None, max_length=200)
    welcome_message_ar: str | None = Field(default=None, max_length=2000)
    welcome_message_en: str | None = Field(default=None, max_length=2000)
    firm_specialties: str | None = Field(default=None, max_length=2000)
    consultation_offer: str | None = Field(default=None, max_length=2000)
    tone_guidelines: str | None = Field(default=None, max_length=2000)
    custom_instructions: str | None = Field(default=None, max_length=4000)
    timezone: str | None = Field(default=None, max_length=64)
    enabled_domains: list[LegalDomain] | None = None
    is_enabled: bool | None = None


class AgentPromptPreview(BaseModel):
    """The exact system prompt the agent will see, after merging the profile.

    The lawyer hits this from the "Teach your agent" page to confirm what
    the agent will actually do — much faster than scanning a QR and texting
    a prospect to test.
    """

    locale: str
    instructions: str
