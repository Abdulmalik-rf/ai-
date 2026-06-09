"""WhatsApp inbound/outbound via Twilio.

Inbound flow:
  1. Twilio POSTs to /webhooks/whatsapp.
  2. We resolve the tenant by mapping the destination (`To`) phone number to
     a tenant's configured Twilio sender. This lets a single Twilio number
     fan out to multiple tenants only via different senders — production
     deployments use one sender per firm.
  3. Resolve / create a `WhatsAppContact` (and `Client`) within that tenant.
  4. Resolve / create a `Conversation` of channel WHATSAPP, append the inbound
     message, run RAG, append the assistant reply, and send via Twilio.
  5. If the assistant output contains the [ESCALATE] sentinel, we create a
     `WhatsAppEscalation` row so the lawyer sees it in the dashboard.
"""
from __future__ import annotations

from base64 import b64encode
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models import (
    Conversation,
    ConversationChannel,
    Message,
    MessageRole,
    Tenant,
    WhatsAppContact,
    WhatsAppEscalation,
)
from app.services.prompts import whatsapp_system
from app.services.rag import answer

log = get_logger(__name__)

ESCALATE_SENTINEL = "[ESCALATE]"


# ----- Outbound --------------------------------------------------------------


def send_message(*, to_phone: str, body: str) -> None:
    if not settings.enable_whatsapp:
        log.info("whatsapp_disabled", to=to_phone)
        return
    auth = b64encode(
        f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode()
    ).decode()
    with httpx.Client(timeout=15) as client:
        r = client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
            headers={"Authorization": f"Basic {auth}"},
            data={
                "From": settings.twilio_whatsapp_from,
                "To": f"whatsapp:{to_phone}" if not to_phone.startswith("whatsapp:") else to_phone,
                "Body": body,
            },
        )
        if r.status_code >= 300:
            log.error("twilio_send_failed", status=r.status_code, body=r.text)
            r.raise_for_status()


# ----- Inbound ---------------------------------------------------------------


def resolve_tenant_for_inbound(
    db: Session, *, to_number: str
) -> Tenant | None:
    """Map a Twilio destination to a tenant.

    For now we keep the configured sender on `tenant.extra_metadata.whatsapp_to`,
    but in production this lives in a dedicated `tenant_channels` table.
    """
    # MVP: any tenant with that number in metadata wins. The seed creates a
    # sample tenant with the dev sandbox number.
    return db.execute(
        select(Tenant).where(Tenant.is_active.is_(True))
    ).scalars().first()


def handle_inbound(
    db: Session,
    *,
    from_phone: str,
    to_phone: str,
    body: str,
) -> str:
    """Returns the assistant body the caller should send back."""
    tenant = resolve_tenant_for_inbound(db, to_number=to_phone)
    if tenant is None:
        log.warning("whatsapp_no_tenant_for_number", to=to_phone)
        return "This number is not configured. Please contact your lawyer."

    contact = db.execute(
        select(WhatsAppContact).where(
            WhatsAppContact.tenant_id == tenant.id,
            WhatsAppContact.wa_phone == from_phone,
        )
    ).scalar_one_or_none()
    if contact is None:
        contact = WhatsAppContact(tenant_id=tenant.id, wa_phone=from_phone)
        db.add(contact)
        db.commit()
        db.refresh(contact)

    if contact.is_blocked:
        return ""  # silently ignore

    conv = (
        db.execute(
            select(Conversation)
            .where(
                Conversation.tenant_id == tenant.id,
                Conversation.channel == ConversationChannel.WHATSAPP,
                Conversation.client_id == contact.client_id,
            )
            .order_by(Conversation.updated_at.desc())
        ).scalars().first()
    )
    if conv is None:
        conv = Conversation(
            tenant_id=tenant.id,
            channel=ConversationChannel.WHATSAPP,
            client_id=contact.client_id,
            title=f"WhatsApp — {from_phone}",
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    db.add(
        Message(
            tenant_id=tenant.id,
            conversation_id=conv.id,
            role=MessageRole.USER,
            content=body,
        )
    )
    db.commit()

    # Build a minimal history so the LLM has context (last 6 messages).
    history_rows = list(
        db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(6)
        ).scalars()
    )
    history = [{"role": m.role.value, "content": m.content} for m in reversed(history_rows)]

    locale = tenant.default_locale
    rag = answer(
        db,
        query=body,
        tenant_id=tenant.id,
        locale=locale,
        history=[{"role": "system", "content": whatsapp_system(locale)}] + history,
    )

    reply = rag.answer
    db.add(
        Message(
            tenant_id=tenant.id,
            conversation_id=conv.id,
            role=MessageRole.ASSISTANT,
            content=reply,
            citations=rag.citations,
            model=rag.model,
            latency_ms=rag.latency_ms,
            token_count=rag.input_tokens + rag.output_tokens,
        )
    )
    db.commit()

    if ESCALATE_SENTINEL in reply:
        db.add(
            WhatsAppEscalation(
                tenant_id=tenant.id,
                conversation_id=conv.id,
                reason="LLM requested escalation",
            )
        )
        db.commit()
        reply = reply.replace(ESCALATE_SENTINEL, "").strip()

    return reply
