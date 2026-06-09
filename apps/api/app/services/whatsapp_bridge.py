"""HTTP client for the Node Baileys bridge (apps/whatsapp-bridge).

The bridge owns the actual WhatsApp Web sockets — one per tenant, keyed by
tenant id. FastAPI talks to it for three things:

  - start a pairing flow for a tenant (returns the QR string the dashboard renders)
  - poll session status
  - send an outbound message after the agent produces a reply

The bridge POSTs *inbound* messages to FastAPI at
`/webhooks/whatsapp-baileys`. Both directions auth with a shared secret in
the `X-Bridge-Secret` header.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class WhatsAppBridgeError(Exception):
    """Raised on bridge HTTP errors. The dashboard surfaces these to admins."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class SessionStatus:
    status: str  # "disconnected" | "pairing" | "connected" | "logged_out" | "error"
    qr: str | None = None
    phone_number: str | None = None
    display_name: str | None = None
    last_disconnect_reason: str | None = None


def _client() -> httpx.Client:
    headers = {"X-Bridge-Secret": settings.whatsapp_bridge_secret}
    return httpx.Client(
        base_url=settings.whatsapp_bridge_url,
        timeout=settings.whatsapp_bridge_timeout_s,
        headers=headers,
    )


def _check_configured() -> None:
    if not settings.enable_whatsapp_baileys:
        raise WhatsAppBridgeError("WhatsApp Baileys integration is disabled.")
    if not settings.whatsapp_bridge_secret:
        raise WhatsAppBridgeError(
            "WHATSAPP_BRIDGE_SECRET is not configured."
        )


def _request(method: str, path: str, **kwargs: Any) -> Any:
    _check_configured()
    try:
        with _client() as c:
            r = c.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        log.error("bridge_unreachable", error=str(exc), method=method, path=path)
        raise WhatsAppBridgeError(
            f"Bridge unreachable: {exc}. Check that the Node service in "
            "apps/whatsapp-bridge is running."
        ) from exc
    if r.status_code >= 400:
        log.error(
            "bridge_error",
            status=r.status_code,
            body=r.text[:300],
            method=method,
            path=path,
        )
        raise WhatsAppBridgeError(
            f"Bridge returned {r.status_code}: {r.text[:200]}",
            status_code=r.status_code,
        )
    if r.status_code == 204:
        return {}
    try:
        return r.json()
    except ValueError:
        return {"raw": r.text}


# ----- Session lifecycle -----------------------------------------------------


def start_session(tenant_id: UUID) -> SessionStatus:
    """Kick off pairing for a tenant.

    Idempotent: if there's already a connected socket for this tenant, the
    bridge returns the current status without re-pairing.
    """
    data = _request(
        "POST", "/sessions/start", json={"tenant_id": str(tenant_id)}
    )
    return _parse_status(data)


def get_session_status(tenant_id: UUID) -> SessionStatus:
    data = _request("GET", f"/sessions/{tenant_id}")
    return _parse_status(data)


def stop_session(tenant_id: UUID) -> None:
    """Logout + delete auth files. Next /start will show a fresh QR."""
    _request("DELETE", f"/sessions/{tenant_id}")


# ----- Outbound -------------------------------------------------------------


def send_message(
    *,
    tenant_id: UUID,
    to_phone: str,
    text: str,
) -> None:
    """Send a text message via the tenant's Baileys socket."""
    _request(
        "POST",
        "/messages/send",
        json={
            "tenant_id": str(tenant_id),
            "to": to_phone,
            "text": text,
        },
    )


# ----- Helpers --------------------------------------------------------------


def _parse_status(data: dict) -> SessionStatus:
    return SessionStatus(
        status=str(data.get("status", "disconnected")),
        qr=data.get("qr"),
        phone_number=data.get("phone_number"),
        display_name=data.get("display_name"),
        last_disconnect_reason=data.get("last_disconnect_reason"),
    )
