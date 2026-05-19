from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def log_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    old_value: Any = None,
    new_value: Any = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        old_value=json.dumps(_serialize(old_value)) if old_value is not None else None,
        new_value=json.dumps(_serialize(new_value)) if new_value is not None else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)
    return event
