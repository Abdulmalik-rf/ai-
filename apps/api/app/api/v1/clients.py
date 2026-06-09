"""CRM clients: standard CRUD."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.deps import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenancy import TenantQuery
from app.models import Client
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate

router = APIRouter()


@router.get("", response_model=list[ClientRead])
def list_clients(
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[ClientRead]:
    rows = TenantQuery.list_(db, Client, principal.tenant_id, limit=limit, offset=offset)
    return [ClientRead.model_validate(r) for r in rows]


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    body: ClientCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ClientRead:
    client = Client(tenant_id=principal.tenant_id, **body.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return ClientRead.model_validate(client)


@router.get("/{client_id}", response_model=ClientRead)
def get_client(
    client_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ClientRead:
    client = TenantQuery.get(db, Client, principal.tenant_id, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return ClientRead.model_validate(client)


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: UUID,
    body: ClientUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> ClientRead:
    client = TenantQuery.get(db, Client, principal.tenant_id, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(client, k, v)
    db.add(client)
    db.commit()
    db.refresh(client)
    return ClientRead.model_validate(client)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_client(
    client_id: UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    client = TenantQuery.get(db, Client, principal.tenant_id, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    db.delete(client)
    db.commit()
