"""Backfill soft-deleted therapist profiles from historical hard-delete audit events."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.models.audit_event import AuditEvent
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User


def _parse_user_id_from_audit_payload(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    for key in ("user_id", "userId", "therapist_user_id"):
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def resolve_user_id_for_deleted_profile(db: Session, profile_id: int, delete_event: AuditEvent | None = None) -> int | None:
    """Best-effort user_id for a hard-deleted profile row."""
    if delete_event is not None:
        uid = _parse_user_id_from_audit_payload(delete_event.old_value)
        if uid is not None:
            return uid

    submit_actor = db.scalar(
        select(AuditEvent.actor_user_id)
        .where(
            AuditEvent.entity_type == "therapist_profile",
            AuditEvent.entity_id == str(profile_id),
            AuditEvent.action == "submit_profile",
            AuditEvent.actor_user_id.is_not(None),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(1)
    )
    if submit_actor:
        return int(submit_actor)

    for action in ("create", "update", "approve_profile", "pause_profile", "resume_profile"):
        event = db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "therapist_profile",
                AuditEvent.entity_id == str(profile_id),
                AuditEvent.action == action,
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(1)
        )
        if not event:
            continue
        for raw in (event.new_value, event.old_value):
            uid = _parse_user_id_from_audit_payload(raw)
            if uid is not None:
                return uid

    return None


def backfill_deleted_profiles_from_audit(db: Session) -> int:
    """
    Recreate DELETED profile stubs for therapist profiles that were hard-deleted.
    Idempotent: skips users who already have a profile row.
    """
    delete_events = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == "therapist_profile",
            AuditEvent.action == "delete",
        )
        .order_by(AuditEvent.created_at.asc())
    ).all()

    created = 0
    seen_users: set[int] = set()

    for event in delete_events:
        if not event.entity_id:
            continue
        try:
            old_profile_id = int(event.entity_id)
        except (TypeError, ValueError):
            continue

        if db.get(TherapistProfile, old_profile_id) is not None:
            continue

        user_id = resolve_user_id_for_deleted_profile(db, old_profile_id, delete_event=event)
        if user_id is None or user_id in seen_users:
            continue

        user = db.get(User, user_id)
        if not user or RoleName.THERAPIST.value not in user.role_names:
            continue

        existing = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
        if existing is not None:
            seen_users.add(user_id)
            continue

        profile = TherapistProfile(
            user_id=user_id,
            display_name=user.full_name,
            status=TherapistProfileStatus.DELETED,
            deleted_at=event.created_at,
            admin_note="Listing restored from audit after historical delete",
        )
        db.add(profile)
        seen_users.add(user_id)
        created += 1

    if created:
        db.flush()
    return created


def audit_delete_snapshot(profile: TherapistProfile) -> dict[str, Any]:
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "status": profile.status.value if profile.status else None,
    }
