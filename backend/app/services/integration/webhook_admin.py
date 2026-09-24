"""Super-admin webhook subscriptions for integration keys."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import log_audit
from app.core.security import hash_password
from app.models.integration import IntegrationWebhook, IntegrationWebhookStatus
from app.models.user import User
from app.services.integration.catalog import normalize_webhook_events
from app.services.integration.client_admin import get_client
from app.services.integration.errors import NotFoundError, ValidationError

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}


def validate_webhook_url(url: str) -> str:
    cleaned = (url or "").strip()
    parsed = urlparse(cleaned)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise ValidationError("Webhook addresses need to start with https://.")
    if len(cleaned) > 512:
        raise ValidationError("That webhook address is too long to store.")
    if host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise ValidationError("Use a public https address for this webhook.")
    return cleaned


def _generate_signing_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


def webhook_to_dict(webhook: IntegrationWebhook) -> dict:
    client = webhook.client
    return {
        "id": webhook.id,
        "integration_client_id": webhook.integration_client_id,
        "client_name": client.name if client else "",
        "url": webhook.url,
        "events": webhook.events,
        "status": webhook.status,
        "created_at": webhook.created_at.isoformat() if webhook.created_at else None,
    }


def list_webhooks(db: Session) -> list[IntegrationWebhook]:
    return list(
        db.scalars(
            select(IntegrationWebhook)
            .options(selectinload(IntegrationWebhook.client))
            .order_by(IntegrationWebhook.id.desc())
        ).all()
    )


def create_webhook(
    db: Session,
    *,
    actor: User,
    integration_client_id: int,
    url: str,
    events: list[str],
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[IntegrationWebhook, str]:
    client = get_client(db, integration_client_id)
    if not client.is_active:
        raise ValidationError("Choose an active API key for this webhook.")
    cleaned_url = validate_webhook_url(url)
    cleaned_events = normalize_webhook_events(events)
    secret = _generate_signing_secret()
    webhook = IntegrationWebhook(
        integration_client_id=client.id,
        url=cleaned_url,
        secret_hash=hash_password(secret),
        events_json=cleaned_events,
        status=IntegrationWebhookStatus.ACTIVE.value,
    )
    db.add(webhook)
    db.flush()
    log_audit(
        db,
        actor_user_id=actor.id,
        integration_client_id=client.id,
        action="integration.webhook_created",
        entity_type="integration_webhook",
        entity_id=webhook.id,
        new_value={"url_host": urlparse(cleaned_url).hostname, "events": cleaned_events},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    webhook.client = client
    return webhook, secret


def update_webhook(
    db: Session,
    *,
    actor: User,
    webhook_id: int,
    url: str | None = None,
    events: list[str] | None = None,
    status: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> IntegrationWebhook:
    webhook = get_webhook(db, webhook_id)
    if url is not None:
        webhook.url = validate_webhook_url(url)
    if events is not None:
        webhook.events_json = normalize_webhook_events(events)
    if status is not None:
        if status not in {IntegrationWebhookStatus.ACTIVE.value, IntegrationWebhookStatus.PAUSED.value}:
            raise ValidationError("A webhook can be active or paused.")
        webhook.status = status
    webhook.updated_at = datetime.now(timezone.utc)
    log_audit(
        db,
        actor_user_id=actor.id,
        integration_client_id=webhook.integration_client_id,
        action="integration.webhook_updated",
        entity_type="integration_webhook",
        entity_id=webhook.id,
        new_value={"status": webhook.status, "events": webhook.events},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return webhook


def rotate_webhook_secret(
    db: Session,
    *,
    actor: User,
    webhook_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[IntegrationWebhook, str]:
    webhook = get_webhook(db, webhook_id)
    secret = _generate_signing_secret()
    webhook.secret_hash = hash_password(secret)
    webhook.updated_at = datetime.now(timezone.utc)
    log_audit(
        db,
        actor_user_id=actor.id,
        integration_client_id=webhook.integration_client_id,
        action="integration.webhook_secret_rotated",
        entity_type="integration_webhook",
        entity_id=webhook.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return webhook, secret


def get_webhook(db: Session, webhook_id: int) -> IntegrationWebhook:
    webhook = db.scalars(
        select(IntegrationWebhook)
        .where(IntegrationWebhook.id == webhook_id)
        .options(selectinload(IntegrationWebhook.client))
    ).first()
    if not webhook:
        raise NotFoundError("Webhook not found")
    return webhook

