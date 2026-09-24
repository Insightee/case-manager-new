"""Structured writes from integration keys. Stored for review; therapist records stay untouched."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.models.integration import IntegrationSignal
from app.services.integration.access import IntegrationPrincipal, require_case_grant, require_scope
from app.services.integration.catalog import DOMAIN_WRITE_SCOPE, SIGNAL_KEYS
from app.services.integration.errors import ForbiddenError, ValidationError
from app.services.integration.rate_limit import check_rate_limit


def submit_signal(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    case_id: int,
    domain: str,
    signal_key: str,
    level: int | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> IntegrationSignal:
    domain_name = (domain or "").strip()
    key = (signal_key or "").strip()
    allowed_keys = SIGNAL_KEYS.get(domain_name)
    if not allowed_keys:
        raise ValidationError("Choose Cases, Sessions, or Goals for a structured write.")
    scope = DOMAIN_WRITE_SCOPE[domain_name]
    if scope not in principal.scopes:
        raise ForbiddenError(f"Missing required scope: {scope}")
    if key not in allowed_keys:
        raise ValidationError("That signal is not in the allowed set for this area.")
    if level is not None and (level < 1 or level > 5):
        raise ValidationError("Level needs to be between 1 and 5.")
    require_scope(principal, scope)
    require_case_grant(db, principal, case_id)
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    row = IntegrationSignal(
        integration_client_id=principal.client_id,
        case_id=case_id,
        domain=domain_name,
        signal_key=key,
        level=level,
        status="pending_review",
    )
    db.add(row)
    db.flush()
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.signal_submitted",
        entity_type="integration_signal",
        entity_id=row.id,
        new_value={"case_id": case_id, "domain": domain_name, "signal_key": key, "level": level, "status": "pending_review"},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return row
