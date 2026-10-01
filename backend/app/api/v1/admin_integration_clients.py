"""Super-admin management of integration keys and webhooks."""
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
    IntegrationWebhookCreate,
    IntegrationWebhookCreated,
    IntegrationWebhookRead,
    IntegrationWebhookUpdate,
)
from app.services.integration import client_admin, webhook_admin
from app.services.integration.errors import IntegrationError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/integration-clients", tags=["admin-integrations"])


@router.get("", response_model=list[IntegrationClientRead])
def list_integration_clients(
    user: User = Depends(require_permission("admin.override")),
    db: Session = Depends(get_db),
):
    return [IntegrationClientRead(**client_admin.client_to_admin_dict(c, db=db)) for c in client_admin.list_clients(db)]


@router.post("", response_model=IntegrationClientCreated, status_code=201)
def create_integration_client(
    payload: IntegrationClientCreate,
    request: Request,
    user: User = Depends(require_permission("admin.override")),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        client, public_id, secret = client_admin.create_client(
            db,
            actor=user,
            name=payload.name,
            scopes=payload.scopes,
            info_access=payload.info_access,
            allow_read=payload.allow_read,
            allow_write=payload.allow_write,
            case_ids=payload.case_ids,
            all_cases=payload.all_cases,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            access_token_minutes=payload.access_token_minutes,
            key_ttl_days=payload.key_ttl_days,
            mcp_enabled=payload.mcp_enabled,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        client = client_admin.get_client(db, client.id)
        body = client_admin.client_to_admin_dict(client, db=db)
        body["public_client_id"] = public_id
        return IntegrationClientCreated(**body, client_id=public_id, client_secret=secret)
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.get("/{client_id}", response_model=IntegrationClientRead)
def get_integration_client(
    client_id: int,
    user: User = Depends(require_permission("admin.override")),
    db: Session = Depends(get_db),
):
    try:
        client = client_admin.get_client(db, client_id)
        body = client_admin.client_to_admin_dict(
            client,
            signals=client_admin.recent_signals(db, client.id),
            db=db,
        )
        return IntegrationClientRead(**body)
    except IntegrationError as exc:
        raise_integration_http(exc)


@router.patch("/{client_id}", response_model=IntegrationClientRead)
def update_integration_client(
    client_id: int,
    payload: IntegrationClientUpdate,
    request: Request,
    user: User = Depends(require_permission("admin.override")),
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
            info_access=payload.info_access,
            allow_read=payload.allow_read,
            allow_write=payload.allow_write,
            case_ids=payload.case_ids,
            all_cases=payload.all_cases,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            access_token_minutes=payload.access_token_minutes,
            key_ttl_days=payload.key_ttl_days,
            mcp_enabled=payload.mcp_enabled,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        client = client_admin.get_client(db, client.id)
        return IntegrationClientRead(**client_admin.client_to_admin_dict(client, db=db))
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.post("/{client_id}/rotate-secret", response_model=IntegrationSecretRotated)
def rotate_integration_secret(
    client_id: int,
    request: Request,
    user: User = Depends(require_permission("admin.override")),
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
    user: User = Depends(require_permission("admin.override")),
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
        return IntegrationClientRead(**client_admin.client_to_admin_dict(client, db=db))
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)
