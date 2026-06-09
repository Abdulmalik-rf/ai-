from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    country: str
    default_locale: str
    is_active: bool
    created_at: datetime


class TenantUpdate(BaseModel):
    name: str | None = None
    default_locale: str | None = None
