"""Admin management of integration clients (human user.manage)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user, get_request_meta
from app.api.deps_integration import raise_integration_http
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.integration import (
    IntegrationClientCreate,
    IntegrationClientCreated,
    IntegrationClientRead,
    IntegrationClientUpdate,
    IntegrationSecretRotated,
)
from app.services.integration import client_admin
from app.services.integration.errors import IntegrationError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/integration-clients", tags=["admin-integrations"])


@router.get("", response_model=list[IntegrationClientRead])
def list_integration_clients(
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    return [IntegrationClientRead(**client_admin.client_to_admin_dict(c)) for c in client_admin.list_clients(db)]


@router.post("", response_model=IntegrationClientCreated, status_code=201)
def create_integration_client(
    payload: IntegrationClientCreate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        client, public_id, secret = client_admin.create_client(
            db,
            actor=user,
            name=payload.name,
            scopes=payload.scopes,
            case_ids=payload.case_ids,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        db.refresh(client)
        return IntegrationClientCreated(
            id=client.id,
            name=client.name,
            status=client.status,
            scopes=client.scopes,
            case_ids=sorted(g.case_id for g in (client.case_grants or [])),
            rate_limit_per_minute=client.rate_limit_per_minute,
            client_id=public_id,
            client_secret=secret,
        )
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/{client_id}", response_model=IntegrationClientRead)
def get_integration_client(
    client_id: int,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    try:
        client = client_admin.get_client(db, client_id)
        return IntegrationClientRead(**client_admin.client_to_admin_dict(client))
    except IntegrationError as exc:
        raise_integration_http(exc)


@router.patch("/{client_id}", response_model=IntegrationClientRead)
def update_integration_client(
    client_id: int,
    payload: IntegrationClientUpdate,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        client = client_admin.update_client(
            db,
            actor=user,
            client_id=client_id,
            name=payload.name,
            scopes=payload.scopes,
            case_ids=payload.case_ids,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        client = client_admin.get_client(db, client.id)
        return IntegrationClientRead(**client_admin.client_to_admin_dict(client))
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.post("/{client_id}/rotate-secret", response_model=IntegrationSecretRotated)
def rotate_integration_secret(
    client_id: int,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        client, public_id, secret = client_admin.rotate_secret(
            db,
            actor=user,
            client_id=client_id,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        return IntegrationSecretRotated(id=client.id, client_id=public_id, client_secret=secret)
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.post("/{client_id}/revoke", response_model=IntegrationClientRead)
def revoke_integration_client(
    client_id: int,
    request: Request,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        client = client_admin.revoke_client_admin(
            db,
            actor=user,
            client_id=client_id,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        client = client_admin.get_client(db, client.id)
        return IntegrationClientRead(**client_admin.client_to_admin_dict(client))
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)
