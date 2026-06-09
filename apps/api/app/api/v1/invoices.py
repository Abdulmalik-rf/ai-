"""Invoices: list + download.

Each tenant sees only their own invoices. Download returns a pre-signed
S3 URL valid for 15 minutes — the dashboard issues a 302 to it.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.models import Invoice, InvoiceStatus
from app.services.storage import presigned_download_url

router = APIRouter()


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: str
    status: InvoiceStatus
    period_start: date
    period_end: date
    issued_at: datetime | None
    paid_at: datetime | None
    currency: str
    subtotal: float
    vat_rate: float
    vat_amount: float
    total: float
    has_pdf: bool

    @classmethod
    def from_row(cls, row: Invoice) -> "InvoiceRead":
        return cls.model_validate(
            {
                "id": row.id,
                "number": row.number,
                "status": row.status,
                "period_start": row.period_start,
                "period_end": row.period_end,
                "issued_at": row.issued_at,
                "paid_at": row.paid_at,
                "currency": row.currency,
                "subtotal": float(row.subtotal),
                "vat_rate": float(row.vat_rate),
                "vat_amount": float(row.vat_amount),
                "total": float(row.total),
                "has_pdf": bool(row.pdf_storage_key),
            }
        )


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[InvoiceRead]:
    rows = list(
        db.execute(
            select(Invoice)
            .where(Invoice.tenant_id == principal.tenant_id)
            .order_by(Invoice.issued_at.desc().nullslast(), Invoice.created_at.desc())
            .limit(min(limit, 200))
            .offset(offset)
        ).scalars()
    )
    return [InvoiceRead.from_row(r) for r in rows]


@router.get("/{invoice_id}/download")
def download_invoice(
    invoice_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    """Issues a pre-signed S3 URL for the rendered PDF."""
    inv = db.execute(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == principal.tenant_id,
        )
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if not inv.pdf_storage_key:
        raise HTTPException(
            status_code=409, detail="PDF for this invoice is not ready yet."
        )
    url = presigned_download_url(inv.pdf_storage_key, expires_in=900)
    return RedirectResponse(url=url, status_code=302)
