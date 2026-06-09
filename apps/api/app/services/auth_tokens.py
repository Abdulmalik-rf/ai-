"""Auth token issuance + revocation: single-use challenges and refresh JWTs.

Three concerns split across distinct functions:

  - issue_auth_token / consume_auth_token: single-use tokens for email
    verification, password reset, invites. Stored as sha256 hashes; raw
    values are returned by `issue_*` so callers can email them.
  - issue_refresh_token / rotate_refresh_token / revoke_refresh_token:
    track active refresh JWTs in `refresh_tokens` so we can rotate on use
    and kill compromised devices.
  - normalize_email: lowercase + strip, used everywhere so logins are
    case-insensitive.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import Role, TokenType
from app.models import AuthToken, AuthTokenKind, RefreshToken, TenantInvite, User

# =============================================================================
# Email normalization
# =============================================================================


def normalize_email(email: str) -> str:
    """Lowercase + strip. Used on every email read/write so authentication
    is case-insensitive and immune to leading/trailing whitespace."""
    return (email or "").strip().lower()


# =============================================================================
# Single-use auth tokens (verify, reset)
# =============================================================================
#
# A new raw token = `secrets.token_urlsafe(32)` (≈43 chars, 256 bits of
# entropy). We store sha256(raw); raw is returned to the caller exactly
# once for emailing.


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IssuedAuthToken:
    raw: str
    record: AuthToken


def issue_auth_token(
    db: Session,
    *,
    kind: AuthTokenKind,
    user_id: UUID | None,
    tenant_id: UUID | None = None,
    email: str | None = None,
    ttl_seconds: int,
    extra_metadata: dict | None = None,
) -> IssuedAuthToken:
    raw = secrets.token_urlsafe(32)
    record = AuthToken(
        kind=kind,
        token_hash=_hash_token(raw),
        user_id=user_id,
        tenant_id=tenant_id,
        email=normalize_email(email) if email else None,
        expires_at=_now() + timedelta(seconds=ttl_seconds),
        extra_metadata=extra_metadata or {},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return IssuedAuthToken(raw=raw, record=record)


class AuthTokenError(Exception):
    """Raised by consume_auth_token on any failure mode (not found, expired,
    used, kind mismatch). We never disclose which one to the caller — too
    much information leaks user enumeration."""


def consume_auth_token(
    db: Session, *, raw: str, expected_kind: AuthTokenKind
) -> AuthToken:
    """Look up by hash, verify, mark used, return the row."""
    if not raw:
        raise AuthTokenError("empty token")
    token_hash = _hash_token(raw)
    record = db.execute(
        select(AuthToken).where(AuthToken.token_hash == token_hash)
    ).scalar_one_or_none()
    if record is None or record.kind != expected_kind:
        raise AuthTokenError("invalid")
    if record.used_at is not None:
        raise AuthTokenError("already used")
    if record.expires_at < _now():
        raise AuthTokenError("expired")
    record.used_at = _now()
    db.commit()
    db.refresh(record)
    return record


def revoke_unused_user_tokens(
    db: Session, *, user_id: UUID, kind: AuthTokenKind
) -> int:
    """Mark all unused tokens of a kind for this user as used.

    Called when a new password-reset / verification token is issued so
    older outstanding ones can't be reused.
    """
    rows = list(
        db.execute(
            select(AuthToken)
            .where(AuthToken.user_id == user_id)
            .where(AuthToken.kind == kind)
            .where(AuthToken.used_at.is_(None))
        ).scalars()
    )
    for r in rows:
        r.used_at = _now()
    if rows:
        db.commit()
    return len(rows)


# =============================================================================
# Tenant invites
# =============================================================================


@dataclass
class IssuedInvite:
    raw: str
    record: TenantInvite


def issue_invite(
    db: Session,
    *,
    tenant_id: UUID,
    email: str,
    role: Role,
    invited_by_user_id: UUID,
    ttl_days: int | None = None,
) -> IssuedInvite:
    ttl = (ttl_days if ttl_days is not None else settings.invite_ttl_days) * 86400
    raw = secrets.token_urlsafe(32)
    record = TenantInvite(
        tenant_id=tenant_id,
        email=normalize_email(email),
        role=role.value,
        token_hash=_hash_token(raw),
        invited_by_user_id=invited_by_user_id,
        expires_at=_now() + timedelta(seconds=ttl),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return IssuedInvite(raw=raw, record=record)


def consume_invite(db: Session, *, raw: str) -> TenantInvite:
    if not raw:
        raise AuthTokenError("empty token")
    token_hash = _hash_token(raw)
    record = db.execute(
        select(TenantInvite).where(TenantInvite.token_hash == token_hash)
    ).scalar_one_or_none()
    if record is None:
        raise AuthTokenError("invalid")
    if record.accepted_at is not None:
        raise AuthTokenError("already accepted")
    if record.revoked_at is not None:
        raise AuthTokenError("revoked")
    if record.expires_at < _now():
        raise AuthTokenError("expired")
    return record


def mark_invite_accepted(db: Session, invite: TenantInvite) -> None:
    invite.accepted_at = _now()
    db.commit()


# =============================================================================
# Refresh tokens (JWT + DB-tracked rotation)
# =============================================================================


def _new_jti() -> str:
    return _uuid.uuid4().hex


def _encode_refresh_jwt(
    *, user_id: UUID, tenant_id: UUID | None, jti: str
) -> tuple[str, datetime]:
    now = _now()
    expires = now + timedelta(days=settings.jwt_refresh_ttl_days)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id) if tenant_id else None,
        "type": TokenType.REFRESH.value,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires


def issue_refresh_token(
    db: Session,
    *,
    user_id: UUID,
    tenant_id: UUID | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    jti = _new_jti()
    token, expires = _encode_refresh_jwt(
        user_id=user_id, tenant_id=tenant_id, jti=jti
    )
    db.add(
        RefreshToken(
            user_id=user_id,
            tenant_id=tenant_id,
            jti=jti,
            expires_at=expires,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    db.commit()
    return token


class RefreshTokenError(Exception):
    """Raised on any refresh-token validation failure. Caller maps to 401."""


def rotate_refresh_token(
    db: Session,
    *,
    raw_token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    """Validate the incoming refresh token, revoke it, mint a new one.

    Returns (user, new_refresh_token). Raises RefreshTokenError on any
    failure — caller turns that into a 401.
    """
    try:
        payload = jwt.decode(
            raw_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError as exc:
        raise RefreshTokenError("invalid signature/format") from exc

    if payload.get("type") != TokenType.REFRESH.value:
        raise RefreshTokenError("wrong token type")
    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        raise RefreshTokenError("missing claims")

    record = db.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    ).scalar_one_or_none()
    if record is None:
        raise RefreshTokenError("unknown jti")
    if record.revoked_at is not None:
        # Reuse of an already-revoked token = compromise signal. Revoke
        # ALL the user's active refresh tokens to be safe.
        revoke_all_user_refresh_tokens(db, user_id=record.user_id)
        raise RefreshTokenError("token replayed; sessions revoked")
    if record.expires_at < _now():
        raise RefreshTokenError("expired")

    user = db.get(User, UUID(sub))
    if user is None or not user.is_active:
        raise RefreshTokenError("user not found or disabled")

    new_jti = _new_jti()
    new_token, new_expires = _encode_refresh_jwt(
        user_id=user.id, tenant_id=user.tenant_id, jti=new_jti
    )
    record.revoked_at = _now()
    record.replaced_by_jti = new_jti
    record.last_used_at = _now()
    db.add(
        RefreshToken(
            user_id=user.id,
            tenant_id=user.tenant_id,
            jti=new_jti,
            expires_at=new_expires,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    db.commit()
    return user, new_token


def revoke_refresh_token(db: Session, *, raw_token: str) -> bool:
    try:
        payload = jwt.decode(
            raw_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},  # allow logout of stale tokens
        )
    except jwt.InvalidTokenError:
        return False
    jti = payload.get("jti")
    if not jti:
        return False
    record = db.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    ).scalar_one_or_none()
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = _now()
    db.commit()
    return True


def revoke_all_user_refresh_tokens(
    db: Session, *, user_id: UUID, except_jti: str | None = None
) -> int:
    rows = list(
        db.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
        ).scalars()
    )
    n = 0
    now = _now()
    for r in rows:
        if except_jti and r.jti == except_jti:
            continue
        r.revoked_at = now
        n += 1
    if n:
        db.commit()
    return n


def list_active_refresh_tokens(
    db: Session, *, user_id: UUID
) -> list[RefreshToken]:
    return list(
        db.execute(
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .where(RefreshToken.expires_at > _now())
            .order_by(RefreshToken.created_at.desc())
        ).scalars()
    )
