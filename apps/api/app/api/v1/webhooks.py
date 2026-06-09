"""Provider webhooks. Mounted at /webhooks (outside the /v1 prefix)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models import (
    AgentProfile,
    Tenant,
    WhatsAppAllowedSender,
    WhatsAppContact,
    WhatsAppSession,
    WhatsAppSessionStatus,
)
from app.schemas.whatsapp import (
    BridgeInboundMessage,
    BridgeInboundReply,
    BridgeSessionUpdate,
)
from app.services.agent import run_whatsapp_turn
from app.services.billing import LimitExceeded, assert_within_limits, record_usage
from app.services.whatsapp import handle_inbound

log = get_logger(__name__)

router = APIRouter()


def _check_bridge_secret(provided: str | None) -> None:
    expected = settings.whatsapp_bridge_secret
    if not expected or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bridge secret.",
        )


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict:
    if stripe_signature is None:
        raise HTTPException(status_code=400, detail="Missing signature.")
    body = await request.body()
    try:
        handle_stripe_webhook(db, body, stripe_signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"received": True}


@router.post("/moyasar")
async def moyasar_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    moyasar_signature: Annotated[
        str | None, Header(alias="X-Moyasar-Signature")
    ] = None,
) -> dict:
    """Moyasar webhook with HMAC-SHA256 signature verification.

    Moyasar signs the raw body with the merchant's webhook secret. We
    verify with `hmac.compare_digest` to avoid timing leaks. When the
    secret is left empty (dev), we accept unsigned payloads but log a
    warning.
    """
    import hashlib
    import hmac

    body = await request.body()
    expected_secret = settings.moyasar_webhook_secret
    if expected_secret:
        if not moyasar_signature:
            raise HTTPException(status_code=400, detail="Missing signature.")
        digest = hmac.new(
            expected_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(digest, moyasar_signature):
            raise HTTPException(status_code=400, detail="Bad signature.")
    else:
        log.warning("moyasar_webhook_unsigned", reason="no MOYASAR_WEBHOOK_SECRET set")

    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid JSON.") from exc
    handle_moyasar_webhook(db, payload)
    return {"received": True}


@router.post("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_webhook(
    db: Annotated[Session, Depends(get_db)],
    From: Annotated[str, Form()] = "",
    To: Annotated[str, Form()] = "",
    Body: Annotated[str, Form()] = "",
) -> str:
    """Twilio inbound webhook (form-encoded).

    We don't reply with TwiML — we use the REST API for outbound from inside
    `handle_inbound` so we can send rich content. Returning empty TwiML keeps
    Twilio happy.
    """
    reply = handle_inbound(
        db,
        from_phone=From.replace("whatsapp:", ""),
        to_phone=To.replace("whatsapp:", ""),
        body=Body,
    )
    if reply:
        # Outbound message is sent via REST inside handle_inbound. The TwiML
        # response below is left empty so Twilio doesn't double-deliver.
        from app.services.whatsapp import send_message
        try:
            send_message(to_phone=From, body=reply)
        except Exception:  # noqa: BLE001
            pass
    return "<Response/>"


# ============================================================================
# Baileys bridge webhooks
# ============================================================================


@router.post("/whatsapp-baileys", response_model=BridgeInboundReply)
def whatsapp_baileys_inbound(
    body: BridgeInboundMessage,
    db: Annotated[Session, Depends(get_db)],
    x_bridge_secret: Annotated[str | None, Header(alias="X-Bridge-Secret")] = None,
) -> BridgeInboundReply:
    """Inbound message from a tenant's Baileys socket.

    The bridge POSTs here whenever a tenant's WhatsApp socket receives a
    new message. We:
      1. Resolve the tenant.
      2. Enforce the per-tenant allowlist (if any rows exist).
      3. Get-or-create a WhatsAppContact, check is_blocked.
      4. Run the agent loop and persist the reply.
      5. Return the reply text — the bridge sends it via Baileys.
    """
    _check_bridge_secret(x_bridge_secret)

    tenant = db.get(Tenant, body.tenant_id)
    if tenant is None or not tenant.is_active:
        log.warning("baileys_inbound_unknown_tenant", tenant_id=str(body.tenant_id))
        raise HTTPException(status_code=404, detail="Tenant not found.")

    from_phone = _normalize_phone(body.from_phone)

    # Allowlist: empty = open. Non-empty = strict.
    allowed_count = (
        db.execute(
            select(WhatsAppAllowedSender).where(
                WhatsAppAllowedSender.tenant_id == tenant.id
            )
        ).scalars().first()
    )
    if allowed_count is not None:
        match = db.execute(
            select(WhatsAppAllowedSender).where(
                WhatsAppAllowedSender.tenant_id == tenant.id,
                WhatsAppAllowedSender.wa_phone == from_phone,
            )
        ).scalar_one_or_none()
        if match is None:
            log.info(
                "baileys_inbound_rejected",
                tenant_id=str(tenant.id),
                from_phone=from_phone,
                reason="not in allowlist",
            )
            return BridgeInboundReply(text="")  # silent drop

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
        return BridgeInboundReply(text="")

    # Per-tenant master switch. The lawyer can pause inbound replies from
    # the dashboard (e.g. while travelling) without unpairing WhatsApp.
    profile = db.execute(
        select(AgentProfile).where(AgentProfile.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if profile is not None and not profile.is_enabled:
        return BridgeInboundReply(text="")

    # Plan limit gate. If the tenant has hit their monthly message cap, send
    # a pre-canned message rather than running the model.
    try:
        assert_within_limits(db, tenant_id=tenant.id, kind="message")
    except LimitExceeded:
        return BridgeInboundReply(
            text=(
                "وصل المكتب للحد الشهري للرسائل. سيتواصل معك المحامي قريبًا."
                if tenant.default_locale == "ar"
                else "Monthly message limit reached. A lawyer will follow up."
            )
        )

    image_urls = [body.image_url] if body.image_url else []
    if body.image_data_url:
        image_urls.append(body.image_data_url)

    reply = run_whatsapp_turn(
        db,
        tenant=tenant,
        contact=contact,
        user_message=body.text,
        user_image_urls=image_urls or None,
    )
    record_usage(db, tenant_id=tenant.id, kind="message")

    escalated = "escalate_to_lawyer" in reply.tools_used
    return BridgeInboundReply(text=reply.text, escalated=escalated)


@router.post("/whatsapp-baileys/session", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def whatsapp_baileys_session_update(
    body: BridgeSessionUpdate,
    db: Annotated[Session, Depends(get_db)],
    x_bridge_secret: Annotated[str | None, Header(alias="X-Bridge-Secret")] = None,
) -> None:
    """Pushed by the bridge whenever the connection state changes.

    Lifecycle: pairing (qr present) → connected → disconnected/logged_out/error.
    We mirror the state onto `whatsapp_sessions` so the dashboard can render
    without round-tripping the bridge on every poll.
    """
    _check_bridge_secret(x_bridge_secret)

    tenant = db.get(Tenant, body.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    session = db.execute(
        select(WhatsAppSession).where(
            WhatsAppSession.tenant_id == body.tenant_id
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if session is None:
        session = WhatsAppSession(
            tenant_id=body.tenant_id,
            status=body.status,
            phone_number=body.phone_number,
            display_name=body.display_name,
            last_qr=body.qr,
            last_qr_at=now if body.qr else None,
            last_connected_at=now if body.status == WhatsAppSessionStatus.CONNECTED else None,
            last_disconnect_reason=body.last_disconnect_reason,
        )
        db.add(session)
    else:
        session.status = body.status
        if body.qr is not None:
            session.last_qr = body.qr
            session.last_qr_at = now
        if body.phone_number:
            session.phone_number = body.phone_number
        if body.display_name:
            session.display_name = body.display_name
        if body.status == WhatsAppSessionStatus.CONNECTED:
            session.last_connected_at = now
            # Once paired, the QR is no longer relevant — clear it.
            session.last_qr = None
        if body.last_disconnect_reason:
            session.last_disconnect_reason = body.last_disconnect_reason
    db.commit()


def _normalize_phone(raw: str) -> str:
    s = raw.strip().replace("whatsapp:", "").replace(" ", "").replace("-", "")
    if s.startswith("+"):
        s = s[1:]
    return s
