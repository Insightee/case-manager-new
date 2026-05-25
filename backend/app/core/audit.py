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


def _extract_case_id_from_payload(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("case_id") or payload.get("caseId")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def infer_audit_case_id(
    *,
    entity_type: str,
    entity_id: str | int | None,
    old_value: Any = None,
    new_value: Any = None,
) -> int | None:
    if entity_type == "case" and entity_id is not None:
        try:
            return int(entity_id)
        except (TypeError, ValueError):
            return None
    for payload in (new_value, old_value):
        cid = _extract_case_id_from_payload(payload)
        if cid is not None:
            return cid
    return _extract_case_id_from_payload(new_value) or _extract_case_id_from_payload(old_value)


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
    case_id: int | None = None,
) -> AuditEvent:
    resolved_case_id = case_id
    if resolved_case_id is None:
        resolved_case_id = infer_audit_case_id(
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
        )
    event = AuditEvent(
        actor_user_id=actor_user_id,
        case_id=resolved_case_id,
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
