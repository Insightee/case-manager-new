"""Admin lifecycle for integration clients (human JWT + user.manage)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import log_audit
from app.core.config import settings
from app.models.case import Case
from app.models.integration import (
    IntegrationCaseGrant,
    IntegrationClient,
    IntegrationClientStatus,
    IntegrationCredential,
)
from app.models.user import User
from app.models.integration import IntegrationSignal
from app.services.integration.auth_service import (
    credential_expiry,
    issue_credential_for_client,
    normalize_scopes,
    revoke_client,
    revoke_credential,
)
from app.services.integration.catalog import (
    build_scopes,
    describe_scopes,
    normalize_access_token_minutes,
    normalize_key_ttl_days,
)
from app.services.integration.errors import NotFoundError, ValidationError


def _resolved_scopes(
    *,
    scopes: list[str] | None,
    info_access: list[str] | None,
    allow_read: bool | None,
    allow_write: bool | None,
) -> list[str]:
    if info_access is not None:
        return build_scopes(
            allow_read=True if allow_read is None else allow_read,
            allow_write=False if allow_write is None else allow_write,
            info_access=info_access,
        )
    return normalize_scopes(scopes)


def create_client(
    db: Session,
    *,
    actor: User,
    name: str,
    scopes: list[str] | None = None,
    info_access: list[str] | None = None,
    allow_read: bool | None = None,
    allow_write: bool | None = None,
    case_ids: list[int] | None = None,
    rate_limit_per_minute: int | None = None,
    access_token_minutes: int | None = None,
    key_ttl_days: int | None = None,
    mcp_enabled: bool | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[IntegrationClient, str, str]:
    name = (name or "").strip()
    if not name or len(name) > 128:
        raise ValidationError("Add a name so you can tell this key apart later.")
    cleaned_scopes = _resolved_scopes(
        scopes=scopes,
        info_access=info_access,
        allow_read=allow_read,
        allow_write=allow_write,
    )
    limit = rate_limit_per_minute or settings.integration_default_rate_limit_per_minute
    if limit < 1 or limit > 1000:
        raise ValidationError("rate_limit_per_minute must be between 1 and 1000.")
    token_minutes = normalize_access_token_minutes(
        access_token_minutes,
        fallback=int(settings.integration_access_token_minutes),
    )
    ttl_days = normalize_key_ttl_days(
        key_ttl_days,
        fallback=int(settings.integration_credential_default_ttl_days),
    )
    client = IntegrationClient(
        name=name,
        status=IntegrationClientStatus.ACTIVE.value,
        scopes_json=cleaned_scopes,
        rate_limit_per_minute=limit,
        access_token_minutes=token_minutes,
        key_ttl_days=ttl_days,
        mcp_enabled=True if mcp_enabled is None else bool(mcp_enabled),
        created_by_user_id=actor.id,
    )
    db.add(client)
    db.flush()
    _replace_case_grants(db, client, case_ids or [])
    issued = issue_credential_for_client(db, client)
    log_audit(
        db,
        actor_user_id=actor.id,
        integration_client_id=client.id,
        action="integration.client_created",
        entity_type="integration_client",
        entity_id=client.id,
        new_value={"name": name, "scopes": cleaned_scopes, "case_ids": case_ids or []},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return client, issued.public_client_id, issued.client_secret


def list_clients(db: Session) -> list[IntegrationClient]:
    return list(
        db.scalars(
            select(IntegrationClient)
            .options(selectinload(IntegrationClient.case_grants), selectinload(IntegrationClient.credentials))
            .order_by(IntegrationClient.id.desc())
        ).all()
    )


def get_client(db: Session, client_id: int) -> IntegrationClient:
    client = db.scalars(
        select(IntegrationClient)
        .where(IntegrationClient.id == client_id)
        .options(selectinload(IntegrationClient.case_grants), selectinload(IntegrationClient.credentials))
    ).first()
    if not client:
        raise NotFoundError("Integration client not found")
    return client


def update_client(
    db: Session,
    *,
    actor: User,
    client_id: int,
    name: str | None = None,
    scopes: list[str] | None = None,
    info_access: list[str] | None = None,
    allow_read: bool | None = None,
    allow_write: bool | None = None,
    case_ids: list[int] | None = None,
    rate_limit_per_minute: int | None = None,
    access_token_minutes: int | None = None,
    key_ttl_days: int | None = None,
    mcp_enabled: bool | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> IntegrationClient:
    client = get_client(db, client_id)
    if not client.is_active:
        raise ValidationError("This key is revoked. Generate a new one to change access.")
    if name is not None:
        name = name.strip()
        if not name or len(name) > 128:
            raise ValidationError("Add a name so you can tell this key apart later.")
        client.name = name
    if info_access is not None or allow_read is not None or allow_write is not None:
        current = describe_scopes(client.scopes)
        client.scopes_json = build_scopes(
            allow_read=current["allow_read"] if allow_read is None else allow_read,
            allow_write=current["allow_write"] if allow_write is None else allow_write,
            info_access=current["info_access"] if info_access is None else info_access,
        )
    elif scopes is not None:
        client.scopes_json = normalize_scopes(scopes)
    if access_token_minutes is not None:
        client.access_token_minutes = normalize_access_token_minutes(
            access_token_minutes,
            fallback=client.access_token_minutes,
        )
    if key_ttl_days is not None:
        client.key_ttl_days = normalize_key_ttl_days(key_ttl_days, fallback=client.key_ttl_days)
        expiry = credential_expiry(client)
        for cred in list(client.credentials or []):
            if cred.revoked_at is None:
                cred.expires_at = expiry
    if mcp_enabled is not None:
        client.mcp_enabled = bool(mcp_enabled)
    if rate_limit_per_minute is not None:
        if rate_limit_per_minute < 1 or rate_limit_per_minute > 1000:
            raise ValidationError("rate_limit_per_minute must be between 1 and 1000.")
        client.rate_limit_per_minute = rate_limit_per_minute
    if case_ids is not None:
        _replace_case_grants(db, client, case_ids)
    client.updated_at = datetime.now(timezone.utc)
    log_audit(
        db,
        actor_user_id=actor.id,
        integration_client_id=client.id,
        action="integration.client_updated",
        entity_type="integration_client",
        entity_id=client.id,
        new_value={
            "name": client.name,
            "scopes": client.scopes,
            "case_ids": case_ids,
            "rate_limit_per_minute": client.rate_limit_per_minute,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return client


def rotate_secret(
    db: Session,
    *,
    actor: User,
    client_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[IntegrationClient, str, str]:
    client = get_client(db, client_id)
    if not client.is_active:
        raise ValidationError("Cannot rotate secret for a revoked client.")
    for cred in list(client.credentials or []):
        if cred.revoked_at is None:
            revoke_credential(db, cred)
    issued = issue_credential_for_client(db, client)
    log_audit(
        db,
        actor_user_id=actor.id,
        integration_client_id=client.id,
        action="integration.credential_rotated",
        entity_type="integration_credential",
        entity_id=issued.credential.id,
        new_value={"credential_id": issued.credential.id},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return client, issued.public_client_id, issued.client_secret


def revoke_client_admin(
    db: Session,
    *,
    actor: User,
    client_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> IntegrationClient:
    client = get_client(db, client_id)
    revoke_client(db, client)
    log_audit(
        db,
        actor_user_id=actor.id,
        integration_client_id=client.id,
        action="integration.client_revoked",
        entity_type="integration_client",
        entity_id=client.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return client


def _replace_case_grants(db: Session, client: IntegrationClient, case_ids: list[int]) -> None:
    unique_ids = sorted({int(c) for c in case_ids})
    if len(unique_ids) > 500:
        raise ValidationError("A maximum of 500 case grants is allowed per client.")
    if unique_ids:
        found = set(db.scalars(select(Case.id).where(Case.id.in_(unique_ids))).all())
        missing = [c for c in unique_ids if c not in found]
        if missing:
            raise ValidationError("One or more case_ids were not found.")
    db.execute(delete(IntegrationCaseGrant).where(IntegrationCaseGrant.integration_client_id == client.id))
    for case_id in unique_ids:
        db.add(IntegrationCaseGrant(integration_client_id=client.id, case_id=case_id))
    db.flush()


def _active_credential(client: IntegrationClient) -> IntegrationCredential | None:
    usable = [cred for cred in (client.credentials or []) if cred.revoked_at is None]
    if not usable:
        return None
    return max(usable, key=lambda cred: cred.id)


def recent_signals(db: Session, client_id: int, *, limit: int = 8) -> list[dict]:
    rows = db.scalars(
        select(IntegrationSignal)
        .where(IntegrationSignal.integration_client_id == client_id)
        .order_by(IntegrationSignal.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "case_id": row.case_id,
            "domain": row.domain,
            "signal_key": row.signal_key,
            "level": row.level,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def client_to_admin_dict(client: IntegrationClient, *, signals: list[dict] | None = None) -> dict:
    active_creds = [c for c in (client.credentials or []) if c.revoked_at is None]
    current = _active_credential(client)
    described = describe_scopes(client.scopes)
    return {
        "id": client.id,
        "name": client.name,
        "status": client.status,
        "scopes": client.scopes,
        "allow_read": described["allow_read"],
        "allow_write": described["allow_write"],
        "info_access": described["info_access"],
        "access_token_minutes": int(client.access_token_minutes or 15),
        "key_ttl_days": int(client.key_ttl_days if client.key_ttl_days is not None else 365),
        "mcp_enabled": bool(client.mcp_enabled),
        "public_client_id": current.public_client_id if current else None,
        "key_expires_at": current.expires_at.isoformat() if current and current.expires_at else None,
        "rate_limit_per_minute": client.rate_limit_per_minute,
        "case_ids": sorted(g.case_id for g in (client.case_grants or [])),
        "active_credential_count": len(active_creds),
        "recent_signals": signals or [],
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }
