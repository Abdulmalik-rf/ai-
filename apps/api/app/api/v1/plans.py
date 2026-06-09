"""Public plans listing (no auth required)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Plan
from app.schemas.subscription import PlanRead

router = APIRouter()


@router.get("", response_model=list[PlanRead])
def list_plans(db: Annotated[Session, Depends(get_db)]) -> list[PlanRead]:
    rows = list(
        db.execute(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_monthly_usd)
        ).scalars()
    )
    return [PlanRead.model_validate(p) for p in rows]
