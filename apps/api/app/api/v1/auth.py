"""Auth: signup, login, refresh, logout, email verify, password reset, sessions.

Production-ready user-facing auth surface:

  POST   /auth/signup
  POST   /auth/login
  POST   /auth/refresh           — rotates refresh token; reuse triggers session purge
  POST   /auth/logout            — revokes one refresh token
  POST   /auth/logout-all        — revokes every active session for the user
  POST   /auth/verify-email
  POST   /auth/resend-verification
  POST   /auth/forgot-password   — never leaks whether the email exists
  POST   /auth/reset-password
  POST   /auth/accept-invite     — finalize a tenant_invite into a real account
  GET    /auth/me
  GET    /auth/sessions          — list active refresh tokens
  DELETE /auth/sessions/{id}     — revoke one

Hardenings layered over the base flow:
  - Email is normalized (lowercased + stripped) on every read/write.
  - Brute-force lockout: after N failed logins for an email, refuses login
    for the remainder of the lockout window (Redis-backed; soft-fails open
    if Redis is down).
  - IP-bucket rate limiting on signup/login/forgot-password.
  - Refresh tokens are tracked in DB so revocation is real (not "wait for
    expiry"). Token-replay = compromise = revoke all the user's sessions.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import Principal, get_current_principal
from app.core.security import (
    Role,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import (
    AuthTokenKind,
    RefreshToken,
    Tenant,
    TenantInvite,
    User,
)
from app.schemas.auth import (
    AcceptInviteRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SessionRead,
    SignupRequest,
    TokenPair,
    TokenRefreshRequest,
    VerifyEmailRequest,
)
from app.schemas.user import UserRead, UserSelfUpdate
from app.core.subdomains import (
    ValidationError as SubdomainValidationError,
    normalize_subdomain,
    validate_subdomain,
)
from app.services.audit import record as audit
from app.services.auth_tokens import (
    AuthTokenError,
    RefreshTokenError,
    consume_auth_token,
    consume_invite,
    issue_auth_token,
    issue_refresh_token,
    list_active_refresh_tokens,
    mark_invite_accepted,
    normalize_email,
    revoke_all_user_refresh_tokens,
    revoke_refresh_token,
    revoke_unused_user_tokens,
    rotate_refresh_token,
)
from app.services.billing import start_trial_subscription
from app.services.email import (
    render_password_reset_email,
    render_verification_email,
    send_email,
)
from app.services.rate_limit import (
    lockout_clear,
    lockout_is_locked,
    lockout_register_failure,
    rate_limit_check,
)
from app.services.staff_notify import normalize_phone, sync_user_allowlist

router = APIRouter()


# =============================================================================
# Helpers
# =============================================================================


def _slugify(text: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return base or "firm"


def _client_ip(request: Request) -> str | None:
    # Trust the first X-Forwarded-For entry behind nginx; fall back to the
    # peer address when running directly.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _enforce_rate_limit(
    request: Request,
    *,
    bucket: str,
    limit: int,
    window_seconds: int,
    key_extra: str | None = None,
) -> None:
    ip = _client_ip(request) or "unknown"
    identifier = f"{ip}:{key_extra}" if key_extra else ip
    allowed, remaining, reset = rate_limit_check(
        bucket=bucket,
        identifier=identifier,
        limit=limit,
        window_seconds=window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Retry in {reset}s.",
            headers={"Retry-After": str(reset)},
        )


def _build_token_pair(
    db: Session,
    *,
    user: User,
    request: Request,
) -> TokenPair:
    refresh = issue_refresh_token(
        db,
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return TokenPair(
        access_token=create_access_token(
            user.id, user.tenant_id, Role(user.role)
        ),
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_min * 60,
    )


def _send_verification_email(db: Session, *, user: User) -> None:
    if user.is_email_verified:
        return
    revoke_unused_user_tokens(
        db, user_id=user.id, kind=AuthTokenKind.EMAIL_VERIFICATION
    )
    issued = issue_auth_token(
        db,
        kind=AuthTokenKind.EMAIL_VERIFICATION,
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        ttl_seconds=settings.email_verification_ttl_hours * 3600,
    )
    rendered = render_verification_email(to=user.email, token=issued.raw)
    send_email(
        to=user.email,
        subject=rendered.subject,
        text=rendered.text,
        html=rendered.html,
    )


# =============================================================================
# Signup / login / refresh / logout
# =============================================================================


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    _enforce_rate_limit(
        request, bucket="signup", limit=10, window_seconds=3600
    )

    email = normalize_email(body.email)

    base_slug = _slugify(body.firm_name)
    slug = base_slug
    counter = 1
    while db.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none():
        counter += 1
        slug = f"{base_slug}-{counter}"

    # Pick the subdomain. Custom value if the user requested one (validated +
    # uniqueness-checked), otherwise default to the slug. Slug is always
    # DNS-safe so it works as a default; collisions tack on the same suffix.
    requested_sub = (body.subdomain or "").strip() if body.subdomain else ""
    if requested_sub:
        sub_norm = normalize_subdomain(requested_sub)
        validation = validate_subdomain(sub_norm)
        if isinstance(validation, SubdomainValidationError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation.message,
            )
        if db.execute(
            select(Tenant.id).where(Tenant.subdomain == sub_norm)
        ).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That subdomain is already in use.",
            )
        subdomain_value = sub_norm
    else:
        subdomain_value = slug
        # Slug-as-subdomain might collide if a previous tenant changed their
        # subdomain to match this slug. Auto-disambiguate.
        sub_counter = 1
        while db.execute(
            select(Tenant.id).where(Tenant.subdomain == subdomain_value)
        ).scalar_one_or_none():
            sub_counter += 1
            subdomain_value = f"{slug}-{sub_counter}"

    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    tenant = Tenant(
        name=body.firm_name,
        slug=slug,
        subdomain=subdomain_value,
        default_locale=body.locale,
    )
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=Role.ADMIN,
        locale=body.locale,
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflict") from exc

    db.refresh(user)
    _send_verification_email(db, user=user)
    # Auto-attach a TRIALING subscription on the BASIC plan so the new
    # tenant can use the dashboard right away. They upgrade via
    # /v1/subscriptions/checkout when they want bigger caps.
    start_trial_subscription(db, tenant=tenant)

    audit(
        db,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action="auth.signup",
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return _build_token_pair(db, user=user, request=request)


@router.post("/login", response_model=TokenPair)
def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    _enforce_rate_limit(
        request, bucket="login", limit=20, window_seconds=300
    )

    email = normalize_email(body.email)

    locked, retry_after = lockout_is_locked(email)
    if locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        attempts = lockout_register_failure(email)
        # Don't disclose which side failed — same message either way.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"X-Login-Attempts": str(attempts)},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled."
        )

    lockout_clear(email)
    audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="auth.login",
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return _build_token_pair(db, user=user, request=request)


@router.post("/refresh", response_model=TokenPair)
def refresh(
    body: TokenRefreshRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    try:
        user, new_refresh = rotate_refresh_token(
            db,
            raw_token=body.refresh_token,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except RefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    return TokenPair(
        access_token=create_access_token(
            user.id, user.tenant_id, Role(user.role)
        ),
        refresh_token=new_refresh,
        expires_in=settings.jwt_access_ttl_min * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def logout(
    body: LogoutRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Revoke the supplied refresh token. Idempotent — silent success if the
    token is unknown / already revoked / malformed."""
    revoked = revoke_refresh_token(db, raw_token=body.refresh_token)
    if revoked:
        audit(
            db,
            tenant_id=None,
            actor_user_id=None,
            action="auth.logout",
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def logout_all(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> None:
    """Revoke every active refresh token for the current user."""
    n = revoke_all_user_refresh_tokens(db, user_id=principal.user.id)
    audit(
        db,
        tenant_id=principal.user.tenant_id,
        actor_user_id=principal.user.id,
        action="auth.logout_all",
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        extra_metadata={"sessions_revoked": n},
    )


# =============================================================================
# Email verification
# =============================================================================


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def verify_email(
    body: VerifyEmailRequest,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    try:
        record = consume_auth_token(
            db, raw=body.token, expected_kind=AuthTokenKind.EMAIL_VERIFICATION
        )
    except AuthTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token.",
        ) from exc
    if record.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is not bound to an account.",
        )
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token."
        )
    user.is_email_verified = True
    db.commit()


@router.post(
    "/resend-verification",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    response_model=None,
)
def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    _enforce_rate_limit(
        request,
        bucket="resend-verification",
        limit=5,
        window_seconds=900,
        key_extra=normalize_email(body.email),
    )
    email = normalize_email(body.email)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    # 202 even when the user doesn't exist or is already verified — no
    # enumeration leak, no surprise to legitimate callers.
    if user is None or user.is_email_verified:
        return
    _send_verification_email(db, user=user)


# =============================================================================
# Password reset
# =============================================================================


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    response_class=Response,
    response_model=None,
)
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    _enforce_rate_limit(
        request,
        bucket="forgot-password",
        limit=5,
        window_seconds=900,
        key_extra=normalize_email(body.email),
    )
    email = normalize_email(body.email)
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    # Always 202, regardless of whether the email is in our DB.
    if user is None or not user.is_active:
        return

    revoke_unused_user_tokens(
        db, user_id=user.id, kind=AuthTokenKind.PASSWORD_RESET
    )
    issued = issue_auth_token(
        db,
        kind=AuthTokenKind.PASSWORD_RESET,
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        ttl_seconds=settings.password_reset_ttl_minutes * 60,
    )
    rendered = render_password_reset_email(to=user.email, token=issued.raw)
    send_email(
        to=user.email,
        subject=rendered.subject,
        text=rendered.text,
        html=rendered.html,
    )


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    try:
        record = consume_auth_token(
            db, raw=body.token, expected_kind=AuthTokenKind.PASSWORD_RESET
        )
    except AuthTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token.",
        ) from exc
    if record.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token."
        )
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token."
        )
    user.hashed_password = hash_password(body.new_password)
    # Reset = nuke every existing session. Forces re-login from every device.
    revoke_all_user_refresh_tokens(db, user_id=user.id)
    db.commit()
    lockout_clear(user.email)
    audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="auth.password_reset",
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


# =============================================================================
# Invites — accept (admin-side issuance lives in /v1/admin/invites)
# =============================================================================


@router.post("/accept-invite", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def accept_invite(
    body: AcceptInviteRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    """Finalize a tenant_invite. Creates the User if the email isn't taken,
    or refuses if the email already belongs to a different tenant."""
    _enforce_rate_limit(
        request, bucket="accept-invite", limit=10, window_seconds=3600
    )

    try:
        invite: TenantInvite = consume_invite(db, raw=body.token)
    except AuthTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite.",
        ) from exc

    existing = db.execute(
        select(User).where(User.email == invite.email)
    ).scalar_one_or_none()
    if existing is not None:
        # The invitee already has an account at another firm. We don't
        # silently move them — refuse, ask them to use a different email.
        if existing.tenant_id != invite.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An account with this email already exists. Use a different "
                    "email to accept the invite."
                ),
            )
        # Same tenant — already a member. Nothing to do.
        mark_invite_accepted(db, invite)
        return _build_token_pair(db, user=existing, request=request)

    user = User(
        tenant_id=invite.tenant_id,
        email=invite.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=Role(invite.role),
        locale=body.locale,
        is_active=True,
        is_email_verified=True,  # invite link is a proof of email control
    )
    db.add(user)
    mark_invite_accepted(db, invite)
    db.commit()
    db.refresh(user)

    audit(
        db,
        tenant_id=invite.tenant_id,
        actor_user_id=user.id,
        action="auth.accept_invite",
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        extra_metadata={"invite_id": str(invite.id)},
    )
    return _build_token_pair(db, user=user, request=request)


# =============================================================================
# Self / sessions
# =============================================================================


@router.get("/me", response_model=UserRead)
def me(principal: Annotated[Principal, Depends(get_current_principal)]) -> UserRead:
    return UserRead.model_validate(principal.user)


@router.patch("/me", response_model=UserRead)
def update_me(
    body: UserSelfUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    """Self-update for the current user: name, locale, and phone number.

    Role/active flags are NOT settable here — those live on /v1/team and
    require admin. Phone-number updates mirror the team-router behaviour:
    the value is normalised to digits-only and reconciled against the
    tenant's WhatsApp allowlist so the AI agent gets to/from access for
    the new number (and loses it for the old one).
    """
    user = principal.user
    payload = body.model_dump(exclude_unset=True)

    previous_phone = user.phone_number
    if "phone_number" in payload:
        payload["phone_number"] = normalize_phone(payload["phone_number"])

    for field, value in payload.items():
        setattr(user, field, value)

    if "phone_number" in payload or "full_name" in payload:
        sync_user_allowlist(db, user=user, previous_phone=previous_phone)

    db.commit()
    db.refresh(user)
    audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="auth.profile_updated",
        target_type="user",
        target_id=str(user.id),
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        extra_metadata={"changed": list(payload.keys())},
    )
    return UserRead.model_validate(user)


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SessionRead]:
    rows = list_active_refresh_tokens(db, user_id=principal.user.id)
    return [SessionRead.model_validate(r) for r in rows]


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def revoke_session(
    session_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    row = db.execute(
        select(RefreshToken).where(
            RefreshToken.id == session_id,
            RefreshToken.user_id == principal.user.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
