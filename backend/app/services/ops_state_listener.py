"""Record status and assignee changes during flush. Reads never write rows."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import event, insert
from sqlalchemy.orm.attributes import get_history

from app.models.daily_log import DailyLog
from app.models.incident import Incident
from app.models.ops_state_transition import OpsStateTransition
from app.models.session import Session as TherapySession
from app.models.support_ticket import SupportTicket

_TRACKED: tuple[tuple[type, str, tuple[str, ...]], ...] = (
    (TherapySession, "session", ("status",)),
    (SupportTicket, "support_ticket", ("status", "assigned_to_user_id")),
    (Incident, "incident", ("status",)),
    (DailyLog, "daily_log", ("approval_status",)),
)

_INSTALLED = False


def _norm(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, enum.Enum):
        return str(value.value)
    return str(value)


def _write(
    connection,
    *,
    entity_type: str,
    entity_id: int,
    field_name: str,
    old_value: object,
    new_value: object,
) -> None:
    connection.execute(
        insert(OpsStateTransition).values(
            entity_type=entity_type,
            entity_id=int(entity_id),
            field_name=field_name,
            old_value=_norm(old_value),
            new_value=_norm(new_value),
            occurred_at=datetime.now(timezone.utc),
        )
    )


def _after_insert(entity_type: str, fields: tuple[str, ...]):
    def _hook(_mapper, connection, target) -> None:
        entity_id = getattr(target, "id", None)
        if entity_id is None:
            return
        for field_name in fields:
            _write(
                connection,
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                old_value=None,
                new_value=getattr(target, field_name, None),
            )

    return _hook


def _after_update(entity_type: str, fields: tuple[str, ...]):
    def _hook(_mapper, connection, target) -> None:
        entity_id = getattr(target, "id", None)
        if entity_id is None:
            return
        for field_name in fields:
            history = get_history(target, field_name)
            if not history.has_changes():
                continue
            old_value = history.deleted[0] if history.deleted else None
            new_value = history.added[0] if history.added else getattr(target, field_name, None)
            if _norm(old_value) == _norm(new_value):
                continue
            _write(
                connection,
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
            )

    return _hook


def install_ops_state_listener() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    for model, entity_type, fields in _TRACKED:
        event.listen(model, "after_insert", _after_insert(entity_type, fields))
        event.listen(model, "after_update", _after_update(entity_type, fields))
    _INSTALLED = True


install_ops_state_listener()
