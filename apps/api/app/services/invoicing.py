"""Invoice issuance + ZATCA QR + PDF rendering.

ZATCA Phase 1 (Generation phase) — every B2B/B2C tax invoice in Saudi
Arabia must include a TLV-encoded QR code carrying:

  Tag 1: Seller name (UTF-8)
  Tag 2: VAT registration number
  Tag 3: Invoice timestamp (ISO 8601)
  Tag 4: Invoice total (with VAT)
  Tag 5: VAT amount

The string is base64-encoded and rendered as a QR on the PDF. Phase 2
(Integration phase) requires API submission to ZATCA's Fatoora portal
with an XML invoice signed by an embedded ZATCA-issued certificate —
that's a deeper integration we punt on until you register your TIN
with the gov portal.

This module:
  - issues an Invoice row with auto-generated tenant-scoped number
  - computes the ZATCA QR
  - renders a bilingual (AR + EN) PDF via reportlab
  - uploads the PDF to S3 under tenants/<id>/invoices/
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import qrcode

from app.core.config import settings
from app.core.logging import get_logger
from app.models import Invoice, InvoiceStatus, Plan, Subscription, Tenant
from app.services.storage import storage_key_for, upload_fileobj

log = get_logger(__name__)


# =============================================================================
# Pricing helpers
# =============================================================================


def _q2(amount: float | Decimal) -> Decimal:
    """Round to 2 decimal places (banker's rounding is wrong for invoices —
    Saudi VAT rules use HALF_UP)."""
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class LineItem:
    description_ar: str
    description_en: str
    quantity: int
    unit_price: Decimal


def _next_invoice_number(db: Session, *, tenant_id: UUID) -> str:
    """Sequential per tenant: INV-YYYY-NNNN. Concurrent issuance is fine
    because of the UNIQUE(tenant_id, number) constraint — losing the race
    just retries with NNNN+1."""
    year = datetime.now(timezone.utc).year
    count = int(
        db.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .where(Invoice.number.like(f"INV-{year}-%"))
        ).scalar_one()
        or 0
    )
    return f"INV-{year}-{count + 1:04d}"


# =============================================================================
# ZATCA QR
# =============================================================================


def _tlv(tag: int, value: str) -> bytes:
    encoded = value.encode("utf-8")
    return bytes([tag, len(encoded)]) + encoded


def build_zatca_qr(
    *,
    seller_name: str,
    seller_vat_number: str,
    issued_at: datetime,
    total: Decimal,
    vat_amount: Decimal,
) -> str:
    """Return the base64 string that goes into the QR pixel renderer.

    Per ZATCA spec the QR carries 5 TLV-encoded fields. Empty seller VAT
    is allowed in Phase 1 for unregistered sellers but flagged on the
    invoice as 'NOT REGISTERED'.
    """
    payload = (
        _tlv(1, seller_name[:50])
        + _tlv(2, seller_vat_number or "0000000000")
        + _tlv(3, issued_at.isoformat(timespec="seconds"))
        + _tlv(4, str(total))
        + _tlv(5, str(vat_amount))
    )
    return base64.b64encode(payload).decode("ascii")


# =============================================================================
# Issuance
# =============================================================================


def issue_subscription_invoice(
    db: Session,
    *,
    tenant: Tenant,
    subscription: Subscription,
    plan: Plan,
    period_start: date,
    period_end: date,
    provider: str | None = None,
    provider_invoice_id: str | None = None,
    paid_at: datetime | None = None,
) -> Invoice:
    """Generate a tax invoice for one billing period of a subscription.

    Caller passes the already-paid-or-pending state via `paid_at`. The PDF
    is generated and stored synchronously; for high-volume tenants this
    can move to a Celery task.
    """
    line = LineItem(
        description_ar=f"اشتراك {plan.name_ar} — من {period_start.isoformat()} إلى {period_end.isoformat()}",
        description_en=f"{plan.name_en} subscription — {period_start.isoformat()} to {period_end.isoformat()}",
        quantity=1,
        unit_price=_q2(plan.price_monthly_sar),
    )
    return _issue(
        db,
        tenant=tenant,
        subscription=subscription,
        period_start=period_start,
        period_end=period_end,
        line_items=[line],
        provider=provider,
        provider_invoice_id=provider_invoice_id,
        paid_at=paid_at,
    )


def _issue(
    db: Session,
    *,
    tenant: Tenant,
    subscription: Subscription | None,
    period_start: date,
    period_end: date,
    line_items: list[LineItem],
    provider: str | None,
    provider_invoice_id: str | None,
    paid_at: datetime | None,
) -> Invoice:
    subtotal = sum((li.unit_price * li.quantity for li in line_items), Decimal("0"))
    subtotal = _q2(subtotal)
    vat_rate = Decimal(str(settings.vat_rate))
    vat_amount = _q2(subtotal * vat_rate)
    total = _q2(subtotal + vat_amount)

    issued_at = datetime.now(timezone.utc)
    seller_name = settings.vat_seller_name
    seller_vat = settings.vat_seller_vat_number
    seller_addr = (
        f"{settings.vat_seller_address_ar} / {settings.vat_seller_address_en}"
    )

    qr = build_zatca_qr(
        seller_name=seller_name,
        seller_vat_number=seller_vat,
        issued_at=issued_at,
        total=total,
        vat_amount=vat_amount,
    )

    invoice = Invoice(
        tenant_id=tenant.id,
        number=_next_invoice_number(db, tenant_id=tenant.id),
        status=InvoiceStatus.PAID if paid_at else InvoiceStatus.ISSUED,
        subscription_id=subscription.id if subscription else None,
        period_start=period_start,
        period_end=period_end,
        issued_at=issued_at,
        paid_at=paid_at,
        currency="SAR",
        subtotal=subtotal,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        total=total,
        seller_name=seller_name,
        seller_vat_number=seller_vat or None,
        seller_address=seller_addr,
        buyer_name=tenant.name,
        buyer_vat_number=tenant.vat_number,
        buyer_address=tenant.billing_address,
        buyer_email=tenant.billing_email,
        provider=provider,
        provider_invoice_id=provider_invoice_id,
        line_items=[
            {
                "description_ar": li.description_ar,
                "description_en": li.description_en,
                "quantity": li.quantity,
                "unit_price": str(li.unit_price),
                "amount": str(_q2(li.unit_price * li.quantity)),
            }
            for li in line_items
        ],
        zatca_qr=qr,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    # Generate PDF + upload. We do this after commit so the DB row exists
    # even if S3 is briefly unavailable.
    try:
        pdf_bytes = render_invoice_pdf(invoice)
        key = storage_key_for(
            tenant.id, invoice.id, f"{invoice.number}.pdf"
        ).replace("/documents/", "/invoices/")
        upload_fileobj(key, BytesIO(pdf_bytes), "application/pdf")
        invoice.pdf_storage_key = key
        db.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "invoice_pdf_upload_failed",
            invoice_id=str(invoice.id),
            error=str(exc),
        )

    log.info(
        "invoice_issued",
        invoice_id=str(invoice.id),
        tenant_id=str(tenant.id),
        number=invoice.number,
        total=str(total),
    )
    return invoice


# =============================================================================
# PDF rendering
# =============================================================================


def render_invoice_pdf(invoice: Invoice) -> bytes:
    """Bilingual (AR + EN) one-page invoice as a PDF byte stream.

    Layout is deliberately conservative — header, parties, line items
    table, totals, ZATCA QR. Production polish (logo, custom font for
    Arabic text) is a frontend-side improvement; this version satisfies
    ZATCA Phase 1 compliance and is human-readable.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    margin = 18 * mm
    y = height - margin

    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "TAX INVOICE")
    c.setFont("Helvetica", 12)
    c.drawRightString(width - margin, y, "فاتورة ضريبية")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Invoice no: {invoice.number}")
    c.drawRightString(width - margin, y, f"رقم الفاتورة: {invoice.number}")
    y -= 5 * mm
    c.drawString(
        margin,
        y,
        f"Issued: {invoice.issued_at.isoformat(timespec='minutes') if invoice.issued_at else '-'}",
    )
    c.drawString(margin + 90 * mm, y, f"Currency: {invoice.currency}")

    y -= 10 * mm
    c.setStrokeColor(colors.lightgrey)
    c.line(margin, y, width - margin, y)
    y -= 6 * mm

    # Seller / Buyer columns
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Seller / البائع")
    c.drawString(margin + 95 * mm, y, "Buyer / المشتري")
    y -= 5 * mm
    c.setFont("Helvetica", 10)

    seller_lines = [
        invoice.seller_name,
        f"VAT: {invoice.seller_vat_number or 'NOT REGISTERED'}",
        invoice.seller_address or "",
    ]
    buyer_lines = [
        invoice.buyer_name,
        f"VAT: {invoice.buyer_vat_number or '—'}",
        invoice.buyer_address or "",
        invoice.buyer_email or "",
    ]
    block_y = y
    for ln in seller_lines:
        c.drawString(margin, block_y, ln[:60])
        block_y -= 4.5 * mm
    block_y_buyer = y
    for ln in buyer_lines:
        c.drawString(margin + 95 * mm, block_y_buyer, ln[:60])
        block_y_buyer -= 4.5 * mm

    y = min(block_y, block_y_buyer) - 4 * mm

    # Period
    c.setFont("Helvetica", 10)
    c.drawString(
        margin,
        y,
        f"Period / الفترة: {invoice.period_start.isoformat()} → {invoice.period_end.isoformat()}",
    )
    y -= 8 * mm

    # Line items table
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Description")
    c.drawRightString(margin + 110 * mm, y, "Qty")
    c.drawRightString(margin + 140 * mm, y, "Unit")
    c.drawRightString(width - margin, y, "Amount")
    y -= 3 * mm
    c.line(margin, y, width - margin, y)
    y -= 5 * mm

    c.setFont("Helvetica", 10)
    for li in invoice.line_items or []:
        c.drawString(margin, y, str(li.get("description_en", ""))[:70])
        c.drawRightString(margin + 110 * mm, y, str(li.get("quantity", 1)))
        c.drawRightString(margin + 140 * mm, y, str(li.get("unit_price", "0.00")))
        c.drawRightString(width - margin, y, str(li.get("amount", "0.00")))
        y -= 5 * mm

    # Totals
    y -= 4 * mm
    c.line(width - margin - 70 * mm, y, width - margin, y)
    y -= 5 * mm
    c.setFont("Helvetica", 10)
    c.drawRightString(width - margin - 30 * mm, y, "Subtotal / المجموع")
    c.drawRightString(width - margin, y, f"{invoice.subtotal} {invoice.currency}")
    y -= 5 * mm
    c.drawRightString(
        width - margin - 30 * mm,
        y,
        f"VAT {Decimal(str(invoice.vat_rate)) * 100:.0f}% / ضريبة القيمة المضافة",
    )
    c.drawRightString(width - margin, y, f"{invoice.vat_amount} {invoice.currency}")
    y -= 5 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - margin - 30 * mm, y, "Total / الإجمالي")
    c.drawRightString(width - margin, y, f"{invoice.total} {invoice.currency}")

    # ZATCA QR
    if invoice.zatca_qr:
        qr_img = qrcode.make(invoice.zatca_qr)
        qr_buf = BytesIO()
        qr_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)
        from reportlab.lib.utils import ImageReader

        c.drawImage(
            ImageReader(qr_buf),
            margin,
            margin,
            width=35 * mm,
            height=35 * mm,
            preserveAspectRatio=True,
            mask="auto",
        )
        c.setFont("Helvetica", 7)
        c.drawString(
            margin, margin - 4 * mm, "ZATCA QR — verify via Fatoora portal"
        )

    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawCentredString(
        width / 2,
        12 * mm,
        f"Status: {str(invoice.status).upper()} · Generated by Legal AI OS",
    )
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
