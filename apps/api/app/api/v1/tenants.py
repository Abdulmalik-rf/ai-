"""Tenant self-service — view + update the firm's settings.

  GET   /v1/tenants/me                 — current tenant details (including subdomain URL)
  PATCH /v1/tenants/me                 — admin: change name / billing / VAT info
  PATCH /v1/tenants/me/subdomain       — admin: change subdomain (validated + audited)

The subdomain change is rate-limited per-tenant to discourage griefing
(rapidly cycling through subdomains to confuse downstream caches /
emails). The dashboard surface is otherwise unrestricted.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import Principal, get_current_principal, require_role
from app.core.security import Role
from app.core.subdomains import (
    ValidationError as SubdomainValidationError,
    normalize_subdomain,
    validate_subdomain,
)
from app.db.session import get_db
from app.models import Tenant
from app.services.audit import record as audit
from app.services.rate_limit import rate_limit_check

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class TenantSelfRead(BaseModel):
    """The tenant's own view of itself. Includes the computed dashboard URL."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    subdomain: str
    country: str
    default_locale: str
    is_active: bool
    vat_number: str | None
    billing_email: str | None
    billing_address: str | None
    onboarding_completed_at: datetime | None
    dashboard_url: str | None  # computed from base_domain + subdomain


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    default_locale: str | None = Field(default=None, pattern=r"^(ar|en)$")
    vat_number: str | None = Field(default=None, max_length=20)
    billing_email: EmailStr | None = None
    billing_address: str | None = Field(default=None, max_length=2000)


class SubdomainUpdate(BaseModel):
    subdomain: str = Field(min_length=3, max_length=60)


# =============================================================================
# Helpers
# =============================================================================


def _serialize(tenant: Tenant) -> TenantSelfRead:
    dashboard_url: str | None = None
    if settings.base_domain and tenant.subdomain:
        scheme = "https" if settings.app_env != "development" else "http"
        dashboard_url = f"{scheme}://{tenant.subdomain}.{settings.base_domain}"
    return TenantSelfRead(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        subdomain=tenant.subdomain,
        country=tenant.country,
        default_locale=tenant.default_locale,
        is_active=tenant.is_active,
        vat_number=tenant.vat_number,
        billing_email=tenant.billing_email,
        billing_address=tenant.billing_address,
        onboarding_completed_at=tenant.onboarding_completed_at,
        dashboard_url=dashboard_url,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/me", response_model=TenantSelfRead)
def get_my_tenant(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> TenantSelfRead:
    if principal.tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant context.",
        )
    return _serialize(principal.tenant)


@router.patch("/me", response_model=TenantSelfRead)
def update_my_tenant(
    body: TenantUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantSelfRead:
    tenant = principal.tenant
    if tenant is None:
        raise HTTPException(status_code=403, detail="No tenant context.")
    payload = body.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    audit(
        db,
        tenant_id=tenant.id,
        actor_user_id=principal.user.id,
        action="tenant.updated",
        target_type="tenant",
        target_id=str(tenant.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        extra_metadata={"changed": list(payload.keys())},
    )
    return _serialize(tenant)


@router.patch("/me/subdomain", response_model=TenantSelfRead)
def change_subdomain(
    body: SubdomainUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require_role(Role.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> TenantSelfRead:
    """Change the tenant's subdomain. Admin only.

    - Rate-limited per tenant: 5 changes per 24 hours so an admin can't
      grief the platform by cycling through subdomains.
    - Validation reuses the same rules as the public /check endpoint.
    - Old subdomain becomes immediately unreachable; existing JWTs keep
      working because they only carry tenant ID, not subdomain.
    """
    tenant = principal.tenant
    if tenant is None:
        raise HTTPException(status_code=403, detail="No tenant context.")

    new_value = normalize_subdomain(body.subdomain)
    if new_value == tenant.subdomain:
        return _serialize(tenant)  # no-op

    # Rate-limit: 5 subdomain changes per tenant per 24h.
    allowed, _, reset = rate_limit_check(
        bucket="subdomain-change",
        identifier=str(tenant.id),
        limit=5,
        window_seconds=24 * 3600,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many subdomain changes for this firm. "
                f"Try again in {reset // 3600 + 1} hours."
            ),
            headers={"Retry-After": str(reset)},
        )

    validation = validate_subdomain(new_value)
    if isinstance(validation, SubdomainValidationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.message,
        )

    old = tenant.subdomain
    tenant.subdomain = new_value
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subdomain is already taken.",
        ) from exc
    db.refresh(tenant)
    audit(
        db,
        tenant_id=tenant.id,
        actor_user_id=principal.user.id,
        action="tenant.subdomain_changed",
        target_type="tenant",
        target_id=str(tenant.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        extra_metadata={"from": old, "to": new_value},
    )
    return _serialize(tenant)
