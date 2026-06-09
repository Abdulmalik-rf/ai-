"""Subdomain availability check.

Public endpoint the signup form polls as the user types a candidate. We
return whether the value is available + the precise reason if not, so the
frontend can render a friendly inline message.

The actual subdomain assignment / change happens in two places:
  - POST /v1/auth/signup (initial)
  - PATCH /v1/tenants/me/subdomain (later)

Both reuse `validate_subdomain` to keep the rules in one place.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.subdomains import (
    ValidationError,
    normalize_subdomain,
    validate_subdomain,
)
from app.db.session import get_db
from app.models import Tenant

router = APIRouter()


class SubdomainCheck(BaseModel):
    subdomain: str
    available: bool
    reason: str | None = None  # validation error code, or "taken"
    message: str | None = None  # human-readable detail


@router.get("/check", response_model=SubdomainCheck)
def check_subdomain(
    subdomain: Annotated[str, Query(min_length=1, max_length=80)],
    db: Annotated[Session, Depends(get_db)],
) -> SubdomainCheck:
    """Return whether `subdomain` is available for a new tenant.

    Public — does not require auth so signup forms can hit it directly.
    Result is conservative: any validation error or taken-row counts as
    unavailable.
    """
    s = normalize_subdomain(subdomain)
    result = validate_subdomain(s)
    if isinstance(result, ValidationError):
        return SubdomainCheck(
            subdomain=s,
            available=False,
            reason=result.code,
            message=result.message,
        )
    existing = db.execute(
        select(Tenant.id).where(Tenant.subdomain == s)
    ).scalar_one_or_none()
    if existing is not None:
        return SubdomainCheck(
            subdomain=s,
            available=False,
            reason="taken",
            message="This subdomain is already in use.",
        )
    return SubdomainCheck(subdomain=s, available=True)
