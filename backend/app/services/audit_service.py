from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import case_scope_check, user_has_permission
from app.models.audit_event import AuditEvent
from app.models.app_usage_chunk import AppUsageChunk
from app.models.case import Case
from app.models.user import User

ACTION_LABELS: dict[str, str] = {
    "approve": "Approved",
    "reject": "Rejected",
    "create": "Created",
    "update": "Updated",
    "delete": "Deleted",
    "submit": "Submitted",
    "update_parent_profile": "Updated parent profile",
    "approve_session_log": "Approved session log",
    "reject_session_log": "Rejected session log",
    "client_status_change": "Client status changed",
    "update_day_type": "Day type changed",
    "update_billing": "Updated billing",
    "billing_rate_change": "Billing amount change",
}


def _billing_audit_detail(old_value: Any, new_value: Any) -> str | None:
    if not isinstance(old_value, dict):
        old_value = {}
    proposed = None
    if isinstance(new_value, dict):
        proposed = new_value.get("proposed_billing") or new_value.get("applied_billing")
        if not isinstance(proposed, dict):
            proposed = new_value
    if not isinstance(proposed, dict):
        proposed = {}
    from app.core.billing_validation import client_amount_inr, resolve_therapist_pay

    parts: list[str] = []
    old_client = client_amount_inr(old_value)
    new_client = client_amount_inr(proposed)
    if round(float(old_client or 0), 2) != round(float(new_client or 0), 2):
        eff = proposed.get("client_billing_effective_from") or "—"
        parts.append(f"Client billing ₹{float(old_client or 0):.0f} → ₹{float(new_client or 0):.0f} (from {eff})")
    old_pay = resolve_therapist_pay(old_value)
    new_pay = resolve_therapist_pay(proposed)
    if round(float(old_pay or 0), 2) != round(float(new_pay or 0), 2):
        eff = proposed.get("therapist_remuneration_effective_from") or "—"
        parts.append(
            f"Therapist remuneration ₹{float(old_pay or 0):.0f} → ₹{float(new_pay or 0):.0f} (from {eff})"
        )
    notes = proposed.get("billing_notes")
    if notes and notes != old_value.get("billing_notes"):
        parts.append(f"Billing notes updated")
    return "; ".join(parts) if parts else None


def humanize_action(action: str) -> str:
    if action in ACTION_LABELS:
        return ACTION_LABELS[action]
    parts = action.replace("_", " ").strip()
    return parts[:1].upper() + parts[1:] if parts else action


def _entity_label(entity_type: str, action: str) -> str:
    et = entity_type.replace("_", " ")
    return f"{humanize_action(action)} {et}"


def _serialize_audit_item(ev: AuditEvent, *, for_therapist: bool = False) -> dict[str, Any]:
    actor = ev.actor if ev.actor_user_id else None
    old_value = _parse_json(ev.old_value)
    new_value = _parse_json(ev.new_value)
    action_label = _entity_label(ev.entity_type, ev.action)
    detail = None
    if ev.action == "update_day_type":
        from app.services.case_day_type_service import audit_detail_for_change

        action_label = "Day type changed"
        if isinstance(new_value, dict):
            detail = audit_detail_for_change(new_value)
    elif ev.action in ("update_billing", "request_low_margin_billing_approval", "approve_low_margin_billing"):
        action_label = (
            "Billing update requested (awaiting approval)"
            if ev.action == "request_low_margin_billing_approval"
            else ("Billing update approved" if ev.action == "approve_low_margin_billing" else "Updated billing")
        )
        detail = _billing_audit_detail(old_value, new_value)
        if for_therapist and detail and "Billing notes" in detail:
            # Therapists: amount changes only
            detail = "; ".join(p for p in detail.split("; ") if "notes" not in p.lower())
    item = {
        "id": ev.id,
        "actor_user_id": ev.actor_user_id,
        "actor_name": actor.full_name if actor else "System",
        "actor_email": actor.email if actor else None,
        "action": ev.action,
        "action_label": action_label,
        "entity_type": ev.entity_type,
        "entity_id": ev.entity_id,
        "case_id": ev.case_id,
        "old_value": None if for_therapist else old_value,
        "new_value": None if for_therapist else new_value,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }
    if detail:
        item["detail"] = detail
    return item


def list_audit_events(
    db: Session,
    user: User,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    case_id: Optional[int] = None,
    limit: int = 50,
    cursor: Optional[int] = None,
) -> dict[str, Any]:
    if not (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "admin.override")
    ):
        raise PermissionError("Insufficient permissions")

    stmt = (
        select(AuditEvent)
        .options(joinedload(AuditEvent.actor))
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == str(entity_id))
    if cursor:
        stmt = stmt.where(AuditEvent.id < cursor)
    if case_id is not None:
        case = db.get(Case, case_id)
        if not case or not case_scope_check(db, user, case):
            raise PermissionError("Case access denied")
        stmt = stmt.where(AuditEvent.case_id == case_id)

    stmt = stmt.limit(min(limit, 100))
    rows = list(db.scalars(stmt).all())
    items = [_serialize_audit_item(ev) for ev in rows]
    next_cursor = rows[-1].id if rows else None
    return {"items": items, "next_cursor": next_cursor}


def _parse_json(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def case_timeline(db: Session, user: User, case_id: int, *, limit: int = 40) -> list[dict]:
    case = db.get(Case, case_id)
    if not case or not case_scope_check(db, user, case):
        raise PermissionError("Case access denied")

    from app.core.permissions import RoleName, has_any_role, has_role
    from app.models.assignment import CaseAssignment
    from app.services import billing_rate_history_service, client_status_service

    is_admin_viewer = has_any_role(
        user,
        RoleName.SUPER_ADMIN,
        RoleName.ADMIN,
        RoleName.MODULE_ADMIN,
        RoleName.CASE_MANAGER,
        RoleName.FINANCE,
        RoleName.HR,
    )
    for_therapist = has_role(user, RoleName.THERAPIST) and not is_admin_viewer

    events: list[dict] = []

    # Case already scope-checked above — load audit without re-requiring admin list perms
    # so therapists can see amount-change rows on their assigned cases.
    audit_stmt = (
        select(AuditEvent)
        .options(joinedload(AuditEvent.actor))
        .where(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(min(limit, 100))
    )
    audit_rows = list(db.scalars(audit_stmt).all())
    for ev in audit_rows:
        item = _serialize_audit_item(ev, for_therapist=for_therapist)
        action = item.get("action") or ""
        if for_therapist:
            if action not in (
                "update_billing",
                "request_low_margin_billing_approval",
                "approve_low_margin_billing",
            ):
                continue
            if not item.get("detail"):
                continue
            item = {**item, "old_value": None, "new_value": None, "source": "audit"}
        else:
            item = {**item, "source": "audit"}
        events.append(item)

    if not for_therapist:
        for item in client_status_service.status_timeline_events(db, case_id, limit=limit):
            events.append(item)

    for item in billing_rate_history_service.timeline_events_for_case(
        db, case_id, for_therapist=for_therapist, limit=limit
    ):
        events.append(item)

    if for_therapist:
        events.sort(key=lambda e: e.get("created_at") or "", reverse=True)
        return events[:limit]

    from app.models.assignment import CaseAssignmentStatus
    from app.models.case_therapist_transition import CaseTherapistTransition, CaseTherapistTransitionStatus

    all_assignments = db.scalars(
        select(CaseAssignment)
        .where(CaseAssignment.case_id == case_id)
        .order_by(CaseAssignment.start_date.asc(), CaseAssignment.id.asc())
    ).all()
    therapist_ids = {a.therapist_user_id for a in all_assignments}
    therapists: dict[int, User] = {}
    if therapist_ids:
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids))).all():
            therapists[u.id] = u

    def _successor(a: CaseAssignment) -> CaseAssignment | None:
        end = a.end_date or a.start_date
        candidates = [
            other
            for other in all_assignments
            if other.id != a.id and other.start_date >= end
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda o: (o.start_date, o.id))

    def _has_prior(a: CaseAssignment) -> bool:
        for other in all_assignments:
            if other.id == a.id:
                continue
            if other.end_date and other.end_date <= a.start_date:
                return True
            if other.start_date < a.start_date and other.status in (
                CaseAssignmentStatus.TRANSFERRED,
                CaseAssignmentStatus.ENDED,
            ):
                return True
        return False

    for a in all_assignments:
        therapist = therapists.get(a.therapist_user_id)
        therapist_label = therapist.full_name if therapist else str(a.therapist_user_id)

        if a.status in (CaseAssignmentStatus.TRANSFERRED, CaseAssignmentStatus.ENDED):
            successor = _successor(a)
            new_label = (
                therapists.get(successor.therapist_user_id).full_name
                if successor and therapists.get(successor.therapist_user_id)
                else (str(successor.therapist_user_id) if successor else "—")
            )
            events.append(
                {
                    "source": "assignment",
                    "id": f"assignment-{a.id}",
                    "action_label": f"Therapist reassigned: {therapist_label} → {new_label}",
                    "detail": a.reason_for_change,
                    "created_at": (a.end_date or a.start_date).isoformat() if (a.end_date or a.start_date) else None,
                    "entity_type": "case_assignment",
                    "entity_id": str(a.id),
                }
            )
        elif a.status == CaseAssignmentStatus.ACTIVE and not _has_prior(a):
            events.append(
                {
                    "source": "assignment",
                    "id": f"assignment-{a.id}",
                    "action_label": f"Therapist assigned: {therapist_label}",
                    "detail": None,
                    "created_at": a.start_date.isoformat() if a.start_date else None,
                    "entity_type": "case_assignment",
                    "entity_id": str(a.id),
                }
            )

    transitions = list(
        db.scalars(
            select(CaseTherapistTransition)
            .where(CaseTherapistTransition.case_id == case_id)
            .order_by(CaseTherapistTransition.created_at.desc())
        ).all()
    )
    for tr in transitions:
        outgoing = therapists.get(tr.outgoing_therapist_user_id)
        incoming = therapists.get(tr.incoming_therapist_user_id)
        outgoing_label = outgoing.full_name if outgoing else str(tr.outgoing_therapist_user_id)
        incoming_label = incoming.full_name if incoming else str(tr.incoming_therapist_user_id)
        dates_label = ", ".join(str(d) for d in (tr.transition_dates or []))
        if tr.status == CaseTherapistTransitionStatus.COMPLETED:
            events.append(
                {
                    "source": "transition",
                    "id": f"transition-{tr.id}-completed",
                    "action_label": f"Transition completed: {outgoing_label} → {incoming_label}",
                    "detail": f"Handover dates: {dates_label}. Billing updated for incoming therapist.",
                    "created_at": tr.completed_at.isoformat() if tr.completed_at else None,
                    "entity_type": "case_therapist_transition",
                    "entity_id": str(tr.id),
                }
            )
        elif tr.status in (
            CaseTherapistTransitionStatus.ACTIVE,
            CaseTherapistTransitionStatus.SCHEDULED,
        ):
            events.append(
                {
                    "source": "transition",
                    "id": f"transition-{tr.id}-active",
                    "action_label": f"Transition handover started: {outgoing_label} + {incoming_label}",
                    "detail": (
                        f"Both therapists submit logs on {dates_label}. "
                        f"Flat pay ₹{float(tr.full_day_pay_inr):.0f} full day / "
                        f"₹{float(tr.half_day_pay_inr):.0f} half day until handover completes."
                    ),
                    "created_at": tr.created_at.isoformat() if tr.created_at else None,
                    "entity_type": "case_therapist_transition",
                    "entity_id": str(tr.id),
                }
            )

    events.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return events[:limit]


def app_usage_summary(
    db: Session,
    user: User,
    *,
    start_at: datetime,
    end_at: datetime,
    portal: Optional[str] = None,
    staff_user_id: Optional[int] = None,
) -> dict[str, Any]:
    if not user_has_permission(user, "admin.override"):
        raise PermissionError("Super admin permission required")

    chunk_stmt = (
        select(AppUsageChunk)
        .where(
            AppUsageChunk.chunk_ended_at >= start_at,
            AppUsageChunk.chunk_ended_at <= end_at,
        )
        .order_by(AppUsageChunk.chunk_ended_at.desc())
    )
    if portal:
        chunk_stmt = chunk_stmt.where(AppUsageChunk.portal == portal)
    if staff_user_id is not None:
        chunk_stmt = chunk_stmt.where(AppUsageChunk.actor_user_id == staff_user_id)

    rows = list(db.scalars(chunk_stmt).all())
    totals: dict[int, dict[str, Any]] = {}
    if rows:
        actor_ids = {r.actor_user_id for r in rows}
        actor_map = {u.id: u for u in db.scalars(select(User).where(User.id.in_(actor_ids))).all()} if actor_ids else {}
        for row in rows:
            actor_id = row.actor_user_id
            if not actor_id:
                continue
            active_seconds = int(row.active_seconds or 0)
            if active_seconds <= 0:
                continue
            actor = actor_map.get(actor_id)
            bucket = totals.setdefault(
                actor_id,
                {
                    "user_id": actor_id,
                    "user_name": actor.full_name if actor else None,
                    "user_email": actor.email if actor else None,
                    "active_seconds": 0,
                    "heartbeats": 0,
                    "last_seen_at": None,
                },
            )
            bucket["active_seconds"] += active_seconds
            bucket["heartbeats"] += 1
            seen_at = row.chunk_ended_at.isoformat() if row.chunk_ended_at else row.created_at.isoformat()
            if seen_at and (bucket["last_seen_at"] is None or seen_at > bucket["last_seen_at"]):
                bucket["last_seen_at"] = seen_at
    else:
        # Backward-compatible fallback for legacy heartbeat rows.
        stmt = (
        select(AuditEvent)
        .options(joinedload(AuditEvent.actor))
        .where(
            AuditEvent.entity_type == "app_usage",
            AuditEvent.action == "app_usage_heartbeat",
            AuditEvent.created_at >= start_at,
            AuditEvent.created_at <= end_at,
        )
        .order_by(AuditEvent.created_at.desc())
    )
    if staff_user_id is not None:
        stmt = stmt.where(AuditEvent.actor_user_id == staff_user_id)

        rows = list(db.scalars(stmt).all())
        for ev in rows:
            payload = _parse_json(ev.new_value) or {}
            if not isinstance(payload, dict):
                continue
            payload_portal = payload.get("portal")
            if portal and payload_portal != portal:
                continue
            actor_id = ev.actor_user_id
            if not actor_id:
                continue
            active_seconds = int(payload.get("active_seconds") or 0)
            if active_seconds <= 0:
                continue
            bucket = totals.setdefault(
                actor_id,
                {
                    "user_id": actor_id,
                    "user_name": ev.actor.full_name if ev.actor else None,
                    "user_email": ev.actor.email if ev.actor else None,
                    "active_seconds": 0,
                    "heartbeats": 0,
                    "last_seen_at": None,
                },
            )
            bucket["active_seconds"] += active_seconds
            bucket["heartbeats"] += 1
            created = ev.created_at.isoformat() if ev.created_at else None
            if created and (bucket["last_seen_at"] is None or created > bucket["last_seen_at"]):
                bucket["last_seen_at"] = created

    items = sorted(totals.values(), key=lambda row: row["active_seconds"], reverse=True)
    return {
        "range": {"start_at": start_at.isoformat(), "end_at": end_at.isoformat(), "portal": portal},
        "items": items,
        "total_active_seconds": sum(item["active_seconds"] for item in items),
    }
