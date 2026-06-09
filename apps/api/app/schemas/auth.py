from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    """Creates a new tenant + first admin user in one shot."""

    firm_name: str = Field(min_length=2, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    locale: str = Field(default="ar", pattern=r"^(ar|en)$")
    # Optional preferred subdomain. When omitted, the auto-generated slug is
    # used. The signup flow validates the value via the same rules as
    # /v1/subdomains/check; collisions return 409.
    subdomain: str | None = Field(default=None, min_length=3, max_length=60)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=8, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class SessionRead(BaseModel):
    """One active refresh token = one device session."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    jti: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    ip_address: str | None
    user_agent: str | None


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    locale: str = Field(default="ar", pattern=r"^(ar|en)$")
