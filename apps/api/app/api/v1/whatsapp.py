"""WhatsApp session router — pairing, status, allowlist.

This is the dashboard-facing API. The lawyer sees a "Connect WhatsApp" button
in the dashboard, clicks it, this router asks the bridge for a QR string,
returns it, the dashboard renders it as an image. The lawyer scans it on
their phone (Settings → Linked devices → Link a device). The bridge pushes
status updates as they happen via /webhooks/whatsapp-baileys/session, which
mirrors them onto the `whatsapp_sessions` row this router reads from.

Subscription gating: pairing requires an active subscription. Existing
sessions still work even if the subscription lapses — they just go read-only
once limits hit (enforced at chat-time, not here).
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Annotated
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import Principal, get_current_principal, require_role
from app.core.security import Role
from app.db.session import get_db
from app.models import (
    AgentProfile,
    Subscription,
    SubscriptionStatus,
    WhatsAppAllowedSender,
    WhatsAppSession,
    WhatsAppSessionStatus,
)
from app.schemas.whatsapp import (
    AgentProfileRead,
    AgentProfileUpdate,
    AgentPromptPreview,
    AllowedSenderCreate,
    AllowedSenderRead,
    SessionStatusRead,
)
from app.services import whatsapp_bridge
from app.services.agent import get_intake_prompt_preview
from app.services.whatsapp_bridge import WhatsAppBridgeError

router = APIRouter()


# =============================================================================
# Session lifecycle
# =============================================================================


@router.post("/session/start", response_model=SessionStatusRead)
def start_session(
    principal: Annotated[
        Principal, Depends(require_role(Role.ADMIN, Role.LAWYER))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> SessionStatusRead:
    """Begin pairing. Returns the QR string the dashboard renders.

    If a session is already connected, this is a no-op and just returns the
    current state (the bridge handles idempotency).
    """
    if not settings.enable_whatsapp_baileys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp pairing is disabled on this deployment.",
        )
    _require_subscription(db, principal)

    try:
        bridge_status = whatsapp_bridge.start_session(principal.tenant_id)
    except WhatsAppBridgeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    session = _upsert_session(
        db,
        tenant_id=principal.tenant_id,
        status_value=WhatsAppSessionStatus(bridge_status.status),
        qr=bridge_status.qr,
        phone_number=bridge_status.phone_number,
        display_name=bridge_status.display_name,
        last_disconnect_reason=bridge_status.last_disconnect_reason,
    )
    return _to_status_read(session)


@router.get("/session/qr.png")
def get_session_qr_png(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    box_size: int = 8,
    border: int = 2,
) -> Response:
    """Server-rendered QR PNG. The dashboard drops this into an `<img>` tag.

    404 once paired (the QR is no longer valid). `Cache-Control: no-store`
    because the QR rotates every ~20s while pairing.
    """
    session = db.execute(
        select(WhatsAppSession).where(
            WhatsAppSession.tenant_id == principal.tenant_id
        )
    ).scalar_one_or_none()
    if (
        session is None
        or session.status != WhatsAppSessionStatus.PAIRING
        or not session.last_qr
    ):
        raise HTTPException(
            status_code=404,
            detail="No QR available. Call POST /v1/whatsapp/session/start.",
        )

    qr = qrcode.QRCode(
        version=None,  # auto-fit to data
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=max(1, min(box_size, 20)),
        border=max(0, min(border, 8)),
    )
    qr.add_data(session.last_qr)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@router.get("/session", response_model=SessionStatusRead)
def get_session(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionStatusRead:
    """Poll the current status. The dashboard hits this on a timer while pairing.

    Reads from the local DB row (kept fresh by the bridge's session-update
    webhook). Falls back to a live bridge query if there's no row yet.
    """
    session = db.execute(
        select(WhatsAppSession).where(
            WhatsAppSession.tenant_id == principal.tenant_id
        )
    ).scalar_one_or_none()

    if session is None:
        # No row yet — ask the bridge directly. This handles the case where
        # the bridge restarted and lost in-memory state but auth is on disk.
        try:
            live = whatsapp_bridge.get_session_status(principal.tenant_id)
        except WhatsAppBridgeError:
            return SessionStatusRead(status=WhatsAppSessionStatus.DISCONNECTED)
        session = _upsert_session(
            db,
            tenant_id=principal.tenant_id,
            status_value=WhatsAppSessionStatus(live.status),
            qr=live.qr,
            phone_number=live.phone_number,
            display_name=live.display_name,
            last_disconnect_reason=live.last_disconnect_reason,
        )
    return _to_status_read(session)


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def stop_session(
    principal: Annotated[
        Principal, Depends(require_role(Role.ADMIN, Role.LAWYER))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Logout + delete bridge auth files. Next /start shows a fresh QR."""
    try:
        whatsapp_bridge.stop_session(principal.tenant_id)
    except WhatsAppBridgeError as exc:
        # We still wipe the local row so the dashboard reflects the intent
        # even if the bridge is unreachable.
        pass

    session = db.execute(
        select(WhatsAppSession).where(
            WhatsAppSession.tenant_id == principal.tenant_id
        )
    ).scalar_one_or_none()
    if session is not None:
        session.status = WhatsAppSessionStatus.DISCONNECTED
        session.qr = None
        session.last_qr = None
        session.phone_number = None
        session.display_name = None
        session.last_disconnect_reason = "Disconnected by user."
        db.commit()


# =============================================================================
# Allowlist (per-tenant phone numbers permitted to message the agent)
# =============================================================================


@router.get("/allowed-senders", response_model=list[AllowedSenderRead])
def list_allowed_senders(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AllowedSenderRead]:
    rows = list(
        db.execute(
            select(WhatsAppAllowedSender)
            .where(WhatsAppAllowedSender.tenant_id == principal.tenant_id)
            .order_by(WhatsAppAllowedSender.created_at.desc())
        ).scalars()
    )
    return [AllowedSenderRead.model_validate(r) for r in rows]


@router.post(
    "/allowed-senders",
    response_model=AllowedSenderRead,
    status_code=status.HTTP_201_CREATED,
)
def add_allowed_sender(
    body: AllowedSenderCreate,
    principal: Annotated[
        Principal, Depends(require_role(Role.ADMIN, Role.LAWYER))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> AllowedSenderRead:
    phone = _normalize_phone(body.wa_phone)
    existing = db.execute(
        select(WhatsAppAllowedSender).where(
            WhatsAppAllowedSender.tenant_id == principal.tenant_id,
            WhatsAppAllowedSender.wa_phone == phone,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return AllowedSenderRead.model_validate(existing)
    row = WhatsAppAllowedSender(
        tenant_id=principal.tenant_id,
        wa_phone=phone,
        label=body.label,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AllowedSenderRead.model_validate(row)


@router.delete(
    "/allowed-senders/{sender_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def remove_allowed_sender(
    sender_id: UUID,
    principal: Annotated[
        Principal, Depends(require_role(Role.ADMIN, Role.LAWYER))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    row = db.execute(
        select(WhatsAppAllowedSender).where(
            WhatsAppAllowedSender.tenant_id == principal.tenant_id,
            WhatsAppAllowedSender.id == sender_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Sender not in allowlist.")
    db.delete(row)
    db.commit()


# =============================================================================
# Helpers
# =============================================================================


def _require_subscription(db: Session, principal: Principal) -> None:
    if not settings.require_subscription_for_whatsapp:
        return
    sub = db.execute(
        select(Subscription).where(Subscription.tenant_id == principal.tenant_id)
    ).scalar_one_or_none()
    if sub is None or sub.status not in (
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.ACTIVE,
    ):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "An active subscription is required to connect WhatsApp. "
                "Please subscribe first."
            ),
        )


def _upsert_session(
    db: Session,
    *,
    tenant_id: UUID,
    status_value: WhatsAppSessionStatus,
    qr: str | None,
    phone_number: str | None,
    display_name: str | None,
    last_disconnect_reason: str | None,
) -> WhatsAppSession:
    session = db.execute(
        select(WhatsAppSession).where(WhatsAppSession.tenant_id == tenant_id)
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if session is None:
        session = WhatsAppSession(
            tenant_id=tenant_id,
            status=status_value,
            phone_number=phone_number,
            display_name=display_name,
            last_qr=qr,
            last_qr_at=now if qr else None,
            last_connected_at=now if status_value == WhatsAppSessionStatus.CONNECTED else None,
            last_disconnect_reason=last_disconnect_reason,
        )
        db.add(session)
    else:
        session.status = status_value
        if qr:
            session.last_qr = qr
            session.last_qr_at = now
        if phone_number:
            session.phone_number = phone_number
        if display_name:
            session.display_name = display_name
        if status_value == WhatsAppSessionStatus.CONNECTED:
            session.last_connected_at = now
        if last_disconnect_reason:
            session.last_disconnect_reason = last_disconnect_reason
    db.commit()
    db.refresh(session)
    return session


def _to_status_read(session: WhatsAppSession) -> SessionStatusRead:
    # Show the QR only while pairing — after pairing it's a stale/secret value.
    qr = session.last_qr if session.status == WhatsAppSessionStatus.PAIRING else None
    return SessionStatusRead(
        status=session.status,
        qr=qr,
        phone_number=session.phone_number,
        display_name=session.display_name,
        last_disconnect_reason=session.last_disconnect_reason,
        last_qr_at=session.last_qr_at,
        last_connected_at=session.last_connected_at,
    )


def _normalize_phone(raw: str) -> str:
    """Strip whatsapp:, spaces, and the leading + so allowlist matches the
    normalized JID we get from the bridge (digits only)."""
    s = raw.strip().replace("whatsapp:", "").replace(" ", "").replace("-", "")
    if s.startswith("+"):
        s = s[1:]
    return s


# =============================================================================
# Agent profile — "Teach your agent" page
# =============================================================================


@router.get("/agent-profile", response_model=AgentProfileRead)
def get_agent_profile(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentProfileRead:
    """Read the tenant's agent tuning. Returns sensible defaults if no row
    exists yet — the dashboard form starts blank."""
    profile = db.execute(
        select(AgentProfile).where(AgentProfile.tenant_id == principal.tenant_id)
    ).scalar_one_or_none()
    if profile is None:
        return AgentProfileRead()
    return AgentProfileRead.model_validate(profile)


@router.put("/agent-profile", response_model=AgentProfileRead)
def update_agent_profile(
    body: AgentProfileUpdate,
    principal: Annotated[
        Principal, Depends(require_role(Role.ADMIN, Role.LAWYER))
    ],
    db: Annotated[Session, Depends(get_db)],
) -> AgentProfileRead:
    """Upsert the tuning. Only fields present in the body are written so the
    dashboard can save partial changes without resending unchanged values."""
    profile = db.execute(
        select(AgentProfile).where(AgentProfile.tenant_id == principal.tenant_id)
    ).scalar_one_or_none()
    if profile is None:
        profile = AgentProfile(tenant_id=principal.tenant_id)
        db.add(profile)

    payload = body.model_dump(exclude_unset=True)
    if "enabled_domains" in payload and payload["enabled_domains"] is not None:
        # Pydantic returned LegalDomain enum members — store the string values.
        payload["enabled_domains"] = [
            d.value if hasattr(d, "value") else str(d)
            for d in payload["enabled_domains"]
        ]
    for field, value in payload.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return AgentProfileRead.model_validate(profile)


@router.get("/agent-profile/preview-prompt", response_model=AgentPromptPreview)
def preview_agent_prompt(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    locale: str = "ar",
) -> AgentPromptPreview:
    """Return the exact assembled system prompt the intake agent will use.

    Useful for the dashboard to show the lawyer what their tuning is doing
    before any prospect ever messages them. `locale` chooses the language
    of the baseline (the firm-set instructions adapt automatically).
    """
    if locale not in ("ar", "en"):
        raise HTTPException(
            status_code=400, detail="locale must be 'ar' or 'en'."
        )
    if principal.tenant is None:
        raise HTTPException(
            status_code=403,
            detail="This action requires a tenant context.",
        )
    instructions = get_intake_prompt_preview(
        db, tenant=principal.tenant, locale=locale
    )
    return AgentPromptPreview(locale=locale, instructions=instructions)
