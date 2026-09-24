"""Client-credentials auth for integration principals."""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import log_audit
from app.core.config import settings
from app.core.security import ALGORITHM, hash_password, verify_password
from app.models.integration import (
    INTEGRATION_SCOPES,
    IntegrationClient,
    IntegrationClientStatus,
    IntegrationCredential,
)
from app.services.integration.access import IntegrationPrincipal
from app.services.integration.catalog import ACCESS_TOKEN_MINUTES
from app.services.integration.errors import FeatureDisabledError, UnauthorizedError, ValidationError

INTEGRATION_TOKEN_TYPE = "integration_access"


def ensure_integration_enabled() -> None:
    if not settings.integration_api_enabled:
        raise FeatureDisabledError()


def _integration_secret() -> str:
    return settings.integration_jwt_secret_key or settings.jwt_secret_key


def generate_public_client_id() -> str:
    return f"ic_{secrets.token_urlsafe(18)}"


def generate_client_secret() -> str:
    return secrets.token_urlsafe(32)


def normalize_scopes(scopes: list[str] | None) -> list[str]:
    if not scopes:
        raise ValidationError("At least one scope is required.")
    cleaned: list[str] = []
    for raw in scopes:
        s = str(raw).strip()
        if s not in INTEGRATION_SCOPES:
            raise ValidationError(f"Unsupported scope: {s}")
        if s not in cleaned:
            cleaned.append(s)
    if not cleaned:
        raise ValidationError("At least one valid scope is required.")
    return cleaned


@dataclass
class IssuedCredential:
    client: IntegrationClient
    credential: IntegrationCredential
    public_client_id: str
    client_secret: str


def access_token_minutes_for_client(client: IntegrationClient) -> int:
    minutes = int(getattr(client, "access_token_minutes", None) or settings.integration_access_token_minutes)
    if minutes not in ACCESS_TOKEN_MINUTES:
        minutes = int(settings.integration_access_token_minutes)
        if minutes not in ACCESS_TOKEN_MINUTES:
            minutes = 15
    return minutes


def credential_expiry(client: IntegrationClient) -> datetime | None:
    days = getattr(client, "key_ttl_days", None)
    if days is None:
        days = settings.integration_credential_default_ttl_days
    if int(days) <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(days=int(days))


def expiry_from_created(created_at: datetime | None, days: int) -> datetime | None:
    """Key lifetime counted from credential creation, not from the latest settings save."""
    if int(days) <= 0:
        return None
    if created_at is None:
        return datetime.now(timezone.utc) + timedelta(days=int(days))
    base = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)
    return base + timedelta(days=int(days))


def create_access_token_for_credential(
    client: IntegrationClient,
    credential: IntegrationCredential,
) -> tuple[str, int]:
    minutes = access_token_minutes_for_client(client)
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload: dict[str, Any] = {
        "sub": str(client.id),
        "exp": expire,
        "type": INTEGRATION_TOKEN_TYPE,
        "client_id": credential.public_client_id,
        "cred_id": credential.id,
        "scopes": client.scopes,
    }
    token = jwt.encode(payload, _integration_secret(), algorithm=ALGORITHM)
    return token, minutes * 60


def authenticate_client_credentials(
    db: Session,
    *,
    public_client_id: str,
    client_secret: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, int, IntegrationClient]:
    ensure_integration_enabled()
    if not public_client_id or not client_secret:
        raise UnauthorizedError("Invalid client credentials")
    cred = db.scalars(
        select(IntegrationCredential)
        .where(IntegrationCredential.public_client_id == public_client_id)
        .options(selectinload(IntegrationCredential.client))
    ).first()
    if not cred or not cred.is_usable:
        raise UnauthorizedError("Invalid client credentials")
    client = cred.client
    if client is None or not client.is_active:
        raise UnauthorizedError("Invalid client credentials")
    if not verify_password(client_secret, cred.secret_hash):
        raise UnauthorizedError("Invalid client credentials")
    token, expires_in = create_access_token_for_credential(client, cred)
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=client.id,
        action="integration.token_issued",
        entity_type="integration_client",
        entity_id=client.id,
        new_value={"scopes": client.scopes, "credential_id": cred.id},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return token, expires_in, client


def decode_integration_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, _integration_secret(), algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != INTEGRATION_TOKEN_TYPE:
        return None
    return payload


def resolve_principal_from_token(db: Session, token: str) -> IntegrationPrincipal:
    ensure_integration_enabled()
    payload = decode_integration_token(token)
    if not payload or not payload.get("sub"):
        raise UnauthorizedError("Invalid token")
    try:
        client_pk = int(payload["sub"])
        cred_id = int(payload.get("cred_id"))
    except (TypeError, ValueError):
        raise UnauthorizedError("Invalid token")
    client = db.get(IntegrationClient, client_pk)
    if not client or not client.is_active:
        raise UnauthorizedError("Invalid token")
    cred = db.get(IntegrationCredential, cred_id)
    if not cred or cred.integration_client_id != client.id or not cred.is_usable:
        raise UnauthorizedError("Invalid or revoked credential")
    token_scopes = payload.get("scopes") or []
    scopes = frozenset(s for s in token_scopes if s in INTEGRATION_SCOPES) & frozenset(client.scopes)
    return IntegrationPrincipal(
        client=client,
        credential_id=cred.id,
        public_client_id=cred.public_client_id,
        scopes=scopes,
    )


def issue_credential_for_client(
    db: Session,
    client: IntegrationClient,
    *,
    expires_at: datetime | None = None,
) -> IssuedCredential:
    public_id = generate_public_client_id()
    raw_secret = generate_client_secret()
    if expires_at is None:
        expires_at = credential_expiry(client)
    cred = IntegrationCredential(
        integration_client_id=client.id,
        public_client_id=public_id,
        secret_hash=hash_password(raw_secret),
        expires_at=expires_at,
    )
    db.add(cred)
    db.flush()
    return IssuedCredential(
        client=client,
        credential=cred,
        public_client_id=public_id,
        client_secret=raw_secret,
    )


def revoke_credential(db: Session, credential: IntegrationCredential) -> None:
    if credential.revoked_at is None:
        credential.revoked_at = datetime.now(timezone.utc)


def revoke_client(db: Session, client: IntegrationClient) -> None:
    client.status = IntegrationClientStatus.REVOKED.value
    for cred in list(client.credentials or []):
        revoke_credential(db, cred)
