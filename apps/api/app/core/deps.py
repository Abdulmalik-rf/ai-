"""FastAPI dependencies — authentication, current user, tenant scope, RBAC.

Every protected route should `Depends(get_current_user)` (or a stricter wrapper
like `require_role(Role.ADMIN)`). The returned `Principal` always carries both
the user and the tenant the request is operating against.

Special semantics: a tenant can be in three modes —
  - active (`is_active=True`): full access
  - read_only (`is_active=False` but no `purge_at`): suspended for non-payment.
    GET requests still work so the firm can see their data + their billing
    page. Mutations return 402 Payment Required.
  - terminated (`purge_at` set): no access at all (we treat it as suspended).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Role, TokenType, decode_token
from app.db.session import get_db
from app.models import Tenant, User


# Routes that remain available even when the tenant is in read-only / suspended
# mode. Adding paths here is intentional — the goal is to let admins see
# their data + their billing page so they can pay and reactivate.
_READ_ONLY_SAFE_PATHS = (
    "/v1/auth/",
    "/v1/subscriptions/",
    "/v1/plans",
    "/v1/team/users",
    "/v1/team/invites",
    "/v1/compliance/",
    "/v1/onboarding/",
    "/health",
    "/metrics",
)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: User
    tenant: Tenant | None
    role: Role

    @property
    def tenant_id(self) -> UUID:
        if self.tenant is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires a tenant context.",
            )
        return self.tenant.id


def _credentials_exc(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Principal:
    if credentials is None:
        raise _credentials_exc("Missing bearer token")

    try:
        payload = decode_token(credentials.credentials)
    except InvalidTokenError as exc:  # noqa: F841
        raise _credentials_exc("Invalid or expired token") from exc

    if payload.get("type") != TokenType.ACCESS.value:
        raise _credentials_exc("Wrong token type")

    user_id = payload.get("sub")
    tenant_id = payload.get("tid")
    role_raw = payload.get("role")

    if not user_id or not role_raw:
        raise _credentials_exc("Malformed token")

    # Single round-trip: pull the user and its tenant in one query instead
    # of two `db.get()` calls. Saves a DB hop on every authenticated request
    # — meaningful on local dev where DB latency dominates `/v1/auth/me`.
    row = db.execute(
        select(User, Tenant)
        .outerjoin(Tenant, Tenant.id == User.tenant_id)
        .where(User.id == UUID(user_id))
    ).first()
    if row is None:
        raise _credentials_exc("User not found or disabled")
    user, tenant = row
    if not user.is_active:
        raise _credentials_exc("User not found or disabled")
    # If the JWT carried a tenant id but the join produced None, the user's
    # tenant binding has changed since the token was minted — refuse rather
    # than silently downgrade.
    if tenant_id and tenant is None:
        raise _credentials_exc("Tenant binding changed; please sign in again")

    # Subdomain ↔ JWT cross-check. If the request came in on a tenant
    # subdomain, the JWT MUST be for that same tenant — otherwise a user
    # from firm-A could send their token to firm-B's dashboard URL and
    # have it work. We refuse rather than silently accept.
    sub_tenant_id = getattr(request.state, "subdomain_tenant_id", None)
    if sub_tenant_id is not None and tenant is not None and tenant.id != sub_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to this firm's subdomain.",
        )

    if tenant is not None:
        if tenant.purge_at is not None:
            # Past the grace window — purge cron is about to scrub it.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant scheduled for deletion.",
            )
        if not tenant.is_active:
            # Suspended (likely non-payment). Allow safe reads + billing
            # routes so the admin can pay; refuse mutations elsewhere.
            path = request.url.path
            method = request.method.upper()
            is_safe_path = any(path.startswith(p) for p in _READ_ONLY_SAFE_PATHS)
            if not (method in _SAFE_METHODS or is_safe_path):
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=(
                        "Account is suspended. Pay your outstanding balance "
                        "via /v1/subscriptions to restore access."
                    ),
                )

    request.state.user_id = user.id
    request.state.tenant_id = tenant.id if tenant else None

    return Principal(user=user, tenant=tenant, role=Role(role_raw))


def require_role(*allowed: Role):
    """Returns a dependency that enforces the principal has one of the listed roles."""

    def _check(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        if principal.role not in allowed and principal.role != Role.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role.",
            )
        return principal

    return _check


def require_super_admin(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    if principal.role != Role.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin only.",
        )
    return principal
