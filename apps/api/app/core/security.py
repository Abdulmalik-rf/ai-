"""Auth primitives: password hashing, JWT issuance, role/tenant checks.

Tokens carry both `sub` (user_id) and `tid` (tenant_id) so every request can be
scoped to its tenant without a second lookup.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class Role(StrEnum):
    """Application-level role granted within a tenant."""

    ADMIN = "admin"          # Tenant admin (firm owner)
    LAWYER = "lawyer"        # Practising lawyer
    STAFF = "staff"          # Paralegal / assistant
    SUPER_ADMIN = "super_admin"  # Platform operator (cross-tenant)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID, tenant_id: UUID | None, role: Role) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id) if tenant_id else None,
        "role": role.value,
        "type": TokenType.ACCESS.value,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_ttl_min)).timestamp()),
    }
    return _encode(payload)


def create_refresh_token(user_id: UUID, tenant_id: UUID | None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tid": str(tenant_id) if tenant_id else None,
        "type": TokenType.REFRESH.value,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.jwt_refresh_ttl_days)).timestamp()),
    }
    return _encode(payload)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
