"""Super-admin webhook subscriptions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_request_meta
from app.api.deps_integration import raise_integration_http
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.integration import (
    IntegrationWebhookCreate,
    IntegrationWebhookCreated,
    IntegrationWebhookRead,
    IntegrationWebhookUpdate,
)
from app.services.integration import webhook_admin
from app.services.integration.errors import IntegrationError

router = APIRouter(prefix="/admin/integration-webhooks", tags=["admin-integrations"])


@router.get("", response_model=list[IntegrationWebhookRead])
def list_webhooks(
    user: User = Depends(require_permission("admin.override")),
    db: Session = Depends(get_db),
):
    return [IntegrationWebhookRead(**webhook_admin.webhook_to_dict(row)) for row in webhook_admin.list_webhooks(db)]


@router.post("", response_model=IntegrationWebhookCreated, status_code=201)
def create_webhook(
    payload: IntegrationWebhookCreate,
    request: Request,
    user: User = Depends(require_permission("admin.override")),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        webhook, secret = webhook_admin.create_webhook(
            db,
            actor=user,
            integration_client_id=payload.integration_client_id,
            url=payload.url,
            events=payload.events,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        webhook = webhook_admin.get_webhook(db, webhook.id)
        body = webhook_admin.webhook_to_dict(webhook)
        return IntegrationWebhookCreated(**body, signing_secret=secret)
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.patch("/{webhook_id}", response_model=IntegrationWebhookRead)
def update_webhook(
    webhook_id: int,
    payload: IntegrationWebhookUpdate,
    request: Request,
    user: User = Depends(require_permission("admin.override")),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        webhook = webhook_admin.update_webhook(
            db,
            actor=user,
            webhook_id=webhook_id,
            url=payload.url,
            events=payload.events,
            status=payload.status,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        return IntegrationWebhookRead(**webhook_admin.webhook_to_dict(webhook))
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)


@router.post("/{webhook_id}/rotate-secret", response_model=IntegrationWebhookCreated)
def rotate_webhook_secret(
    webhook_id: int,
    request: Request,
    user: User = Depends(require_permission("admin.override")),
    db: Session = Depends(get_db),
):
    meta = get_request_meta(request)
    try:
        webhook, secret = webhook_admin.rotate_webhook_secret(
            db,
            actor=user,
            webhook_id=webhook_id,
            ip_address=meta["ip_address"],
            user_agent=meta["user_agent"],
        )
        db.commit()
        body = webhook_admin.webhook_to_dict(webhook)
        return IntegrationWebhookCreated(**body, signing_secret=secret)
    except IntegrationError as exc:
        db.rollback()
        raise_integration_http(exc)
