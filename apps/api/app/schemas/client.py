from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["person", "company"] = "person"
    status: Literal["lead", "prospect", "active", "archived"] | None = None
    national_id: str | None = None
    cr_number: str | None = None
    vat_number: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    lead_source: str | None = None
    referred_by: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)


class ClientUpdate(BaseModel):
    name: str | None = None
    kind: Literal["person", "company"] | None = None
    status: Literal["lead", "prospect", "active", "archived"] | None = None
    national_id: str | None = None
    cr_number: str | None = None
    vat_number: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    lead_source: str | None = None
    referred_by: str | None = None
    kyc_completed_at: datetime | None = None
    kyc_notes: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: str
    status: str
    national_id: str | None
    cr_number: str | None
    vat_number: str | None
    email: str | None
    phone: str | None
    address: str | None
    city: str | None
    lead_source: str | None
    referred_by: str | None
    kyc_completed_at: datetime | None
    kyc_notes: str | None
    notes: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
