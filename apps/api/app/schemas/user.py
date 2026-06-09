from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import Role


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    email: EmailStr
    full_name: str
    role: Role
    locale: str
    is_active: bool
    is_email_verified: bool
    phone_number: str | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
    locale: str | None = None
    role: Role | None = None
    phone_number: str | None = Field(default=None, max_length=32)


class UserSelfUpdate(BaseModel):
    """Fields the current user is allowed to change about their own account.

    Role/active flags are excluded — those live on team-admin endpoints so
    users can't escalate or self-deactivate.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    locale: str | None = Field(default=None, pattern=r"^(ar|en)$")
    phone_number: str | None = Field(default=None, max_length=32)
