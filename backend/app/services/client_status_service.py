from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.permissions import RoleName, user_has_permission
from app.models.audit_event import AuditEvent
from app.models.case import Case, CaseStatus
from app.models.case_client_status_audit import CaseClientStatusAudit
from app.models.user import User
from app.services.parent_service import (
    child_ids_for_parent,
    primary_parent_user_id_for_child,
)
# Closed end-state uses CLOSED (same side effects as legacy DEACTIVATED).
ADMIN_ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    CaseStatus.PENDING_ALLOTMENT.value: [CaseStatus.ACTIVE.value],
    CaseStatus.ACTIVE.value: [
        CaseStatus.SUSPENDED.value,
        CaseStatus.PENDING_REPLACEMENT.value,
        CaseStatus.CLOSED.value,
    ],
    CaseStatus.SUSPENDED.value: [
        CaseStatus.ACTIVE.value,
        CaseStatus.CLOSED.value,
    ],
    CaseStatus.PENDING_REPLACEMENT.value: [
        CaseStatus.ACTIVE.value,
        CaseStatus.CLOSED.value,
    ],
    # Reopen → pending allotment so a therapist must be reassigned.
    CaseStatus.CLOSED.value: [CaseStatus.PENDING_ALLOTMENT.value],
    CaseStatus.DEACTIVATED.value: [CaseStatus.PENDING_ALLOTMENT.value],
}

_TERMINAL_CLOSE_STATUSES = frozenset(
    {CaseStatus.CLOSED.value, CaseStatus.DEACTIVATED.value}
)
_REOPEN_TARGET_STATUSES = frozenset(
    {CaseStatus.PENDING_ALLOTMENT.value, CaseStatus.ACTIVE.value}
)
_PARENT_PORTAL_AUTO_SUSPEND = "parent_portal_auto_suspend"
_PARENT_PORTAL_AUTO_REACTIVATE = "parent_portal_auto_reactivate"
_MANUAL_USER_DEACTIVATE = "deactivate"
_REOPEN_ROLES = frozenset(
    {
        RoleName.SUPER_ADMIN.value,
        RoleName.MODULE_ADMIN.value,
        RoleName.ADMIN.value,
        RoleName.HR.value,
    }
)

AGEING_WARN_DAYS = 7  # configurable threshold for highlighting


def user_can_manage_client_status(user: User) -> bool:
    return user_has_permission(user, "case.update") or user_has_permission(
        user, "case.status_manage"
    )


def user_can_reopen_case(user: User) -> bool:
    if user_has_permission(user, "admin.override"):
        return True
    return bool(set(user.role_names) & _REOPEN_ROLES)


def _cancel_future_bookings(db: Session, case_id: int) -> None:
    """Reuse booking cleanup for suspend/deactivate paths."""
    from app.services.case_close_service import cleanup_future_bookings

    cleanup_future_bookings(db, case_id)


def _is_reopen_transition(current_status: str, new_status: str) -> bool:
    return (
        current_status in _TERMINAL_CLOSE_STATUSES
        and new_status == CaseStatus.PENDING_ALLOTMENT.value
    )


def _is_close_transition(new_status: str) -> bool:
    return new_status == CaseStatus.CLOSED.value


def _parent_user_for_case(db: Session, case: Case) -> User | None:
    parent_user_id = primary_parent_user_id_for_child(db, case.child_id)
    if not parent_user_id:
        return None
    return db.get(User, parent_user_id)


def _parent_has_other_non_terminal_cases(
    db: Session, parent_user_id: int, *, exclude_case_id: int
) -> bool:
    child_ids = child_ids_for_parent(db, parent_user_id)
    if not child_ids:
        return False
    other = db.scalars(
        select(Case.id)
        .where(
            Case.child_id.in_(child_ids),
            Case.id != exclude_case_id,
            Case.status.notin_(
                [CaseStatus.CLOSED, CaseStatus.DEACTIVATED],
            ),
        )
        .limit(1)
    ).first()
    return other is not None


def _latest_parent_suspend_audit_action(db: Session, parent_user_id: int) -> str | None:
    """Most recent auto-suspend or manual deactivate audit for this parent user."""
    event = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == "user",
            AuditEvent.entity_id == str(parent_user_id),
            AuditEvent.action.in_(
                (_PARENT_PORTAL_AUTO_SUSPEND, _MANUAL_USER_DEACTIVATE),
            ),
        )
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
    ).first()
    return event.action if event else None


def _maybe_auto_suspend_parent_portal(db: Session, case: Case, actor: User) -> None:
    """Silent: disable parent login when all their cases are CLOSED/DEACTIVATED."""
    parent = _parent_user_for_case(db, case)
    if not parent or not parent.is_active:
        return
    if _parent_has_other_non_terminal_cases(db, parent.id, exclude_case_id=case.id):
        return
    parent.is_active = False
    log_audit(
        db,
        actor_user_id=actor.id,
        action=_PARENT_PORTAL_AUTO_SUSPEND,
        entity_type="user",
        entity_id=parent.id,
        case_id=case.id,
        new_value={
            "is_active": False,
            "cause": "all_cases_closed_or_deactivated",
            "case_id": case.id,
        },
    )


def _maybe_auto_reactivate_parent_portal(db: Session, case: Case, actor: User) -> None:
    """Silent: restore parent login only if last suspend was auto (not manual)."""
    parent = _parent_user_for_case(db, case)
    if not parent or parent.is_active:
        return
    last_suspend = _latest_parent_suspend_audit_action(db, parent.id)
    if last_suspend != _PARENT_PORTAL_AUTO_SUSPEND:
        return
    parent.is_active = True
    log_audit(
        db,
        actor_user_id=actor.id,
        action=_PARENT_PORTAL_AUTO_REACTIVATE,
        entity_type="user",
        entity_id=parent.id,
        case_id=case.id,
        new_value={
            "is_active": True,
            "cause": "case_reopened_or_activated",
            "case_id": case.id,
        },
    )


def change_client_status(
    db: Session,
    case: Case,
    user: User,
    new_status: str,
    effective_date: date,
    reason: str,
    internal_notes: Optional[str] = None,
) -> CaseClientStatusAudit:
    """Admin/HR-direct status change with full audit trail. Caller must commit."""
    current_status = case.status.value if hasattr(case.status, "value") else str(case.status)
    new_status_upper = new_status.upper()

    # Validate transition
    allowed = ADMIN_ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status_upper not in allowed:
        raise ValueError(
            f"Cannot transition from {current_status} to {new_status_upper}. "
            f"Allowed: {allowed or ['none (terminal state)']}"
        )

    if _is_reopen_transition(current_status, new_status_upper) and not user_can_reopen_case(
        user
    ):
        raise ValueError("Only admin or HR can reopen a closed case")

    # Validate inputs
    if not effective_date:
        raise ValueError("Effective date is required")
    if not reason or len(reason.strip()) < 5:
        raise ValueError("Reason must be at least 5 characters")

    # Validate new_status is a known CaseStatus
    try:
        new_case_status = CaseStatus(new_status_upper)
    except ValueError:
        raise ValueError(f"Unknown status: {new_status_upper}")

    # Side effects: cancel future bookings for non-active statuses
    if new_status_upper in (
        CaseStatus.SUSPENDED.value,
        CaseStatus.PENDING_REPLACEMENT.value,
    ):
        _cancel_future_bookings(db, case.id)
    elif _is_close_transition(new_status_upper):
        from app.services.case_close_service import (
            apply_case_closed_side_effects,
            assert_no_blocking_invoices_for_close,
        )

        assert_no_blocking_invoices_for_close(db, case.id)
        apply_case_closed_side_effects(db, case)

    # Create audit row
    audit = CaseClientStatusAudit(
        case_id=case.id,
        previous_status=current_status,
        new_status=new_status_upper,
        effective_date=effective_date,
        reason=reason.strip(),
        internal_notes=internal_notes.strip() if internal_notes else None,
        changed_by_user_id=user.id,
        changed_at=datetime.now(timezone.utc),
    )
    db.add(audit)

    # Update the case
    case.status = new_case_status
    case.status_effective_date = effective_date
    case.status_reason = reason.strip()
    case.status_changed_by_user_id = user.id

    db.flush()

    # Parent portal login: silent auto-suspend / auto-reactivate (audit only, no email).
    if new_status_upper in _TERMINAL_CLOSE_STATUSES:
        _maybe_auto_suspend_parent_portal(db, case, user)
    elif new_status_upper in _REOPEN_TARGET_STATUSES:
        _maybe_auto_reactivate_parent_portal(db, case, user)

    db.flush()
    return audit


def list_audit_for_case(db: Session, case_id: int, limit: int = 50) -> list[dict]:
    """Return audit trail for a case, newest first, with ageing computed."""
    rows = db.scalars(
        select(CaseClientStatusAudit)
        .where(CaseClientStatusAudit.case_id == case_id)
        .order_by(CaseClientStatusAudit.changed_at.desc())
        .limit(limit)
    ).all()
    today = date.today()
    out = []
    for r in rows:
        changer = db.get(User, r.changed_by_user_id)
        ageing_days = (today - r.effective_date).days if r.effective_date else None
        # Only show ageing warning for statuses that are still active concerns
        show_ageing = r.new_status in (
            CaseStatus.SUSPENDED.value,
            CaseStatus.PENDING_REPLACEMENT.value,
        )
        out.append({
            "id": r.id,
            "caseId": r.case_id,
            "previousStatus": r.previous_status,
            "newStatus": r.new_status,
            "effectiveDate": r.effective_date.isoformat() if r.effective_date else None,
            "reason": r.reason,
            "internalNotes": r.internal_notes,
            "changedBy": changer.full_name if changer else None,
            "changedAt": r.changed_at.isoformat() if r.changed_at else None,
            "ageingDays": ageing_days if show_ageing else None,
            "ageingWarning": show_ageing and ageing_days is not None and ageing_days > AGEING_WARN_DAYS,
        })
    return out


def status_timeline_events(db: Session, case_id: int, *, limit: int = 40) -> list[dict]:
    """Serialize client-status audit rows for the case activity timeline."""
    rows = db.scalars(
        select(CaseClientStatusAudit)
        .where(CaseClientStatusAudit.case_id == case_id)
        .order_by(CaseClientStatusAudit.changed_at.desc())
        .limit(limit)
    ).all()
    events: list[dict] = []
    for r in rows:
        changer = db.get(User, r.changed_by_user_id)
        eff = r.effective_date.isoformat() if r.effective_date else None
        if r.new_status == CaseStatus.CLOSED.value:
            action_label = f"Case closed (effective {eff})" if eff else "Case closed"
        elif _is_reopen_transition(r.previous_status, r.new_status):
            action_label = f"Case reopened (effective {eff})" if eff else "Case reopened"
        elif (
            r.previous_status == CaseStatus.PENDING_ALLOTMENT.value
            and r.new_status == CaseStatus.ACTIVE.value
        ):
            action_label = f"Case allotted (effective {eff})" if eff else "Case allotted"
        else:
            action_label = f"Status changed: {r.previous_status} → {r.new_status}"
        if r.reason:
            action_label = f"{action_label} — {r.reason}"
        events.append(
            {
                "source": "status",
                "id": f"status-{r.id}",
                "action": "client_status_change",
                "action_label": action_label,
                "actor_name": changer.full_name if changer else "System",
                "actor_user_id": r.changed_by_user_id,
                "entity_type": "case_status",
                "entity_id": str(r.id),
                "case_id": case_id,
                "created_at": r.changed_at.isoformat() if r.changed_at else None,
                "effective_date": eff,
                "reason": r.reason,
                "previous_status": r.previous_status,
                "new_status": r.new_status,
            }
        )
    return events


def get_case_billing_cutoff(case: Case) -> Optional[date]:
    """Returns the billing cutoff date if the case status blocks billing. None for active billing."""
    billing_blocked_statuses = {
        CaseStatus.SUSPENDED.value,
        CaseStatus.PENDING_REPLACEMENT.value,
        CaseStatus.DEACTIVATED.value,
        CaseStatus.CLOSED.value,
    }
    current = case.status.value if hasattr(case.status, "value") else str(case.status)
    if current in billing_blocked_statuses:
        return case.status_effective_date
    return None


def assert_case_not_deactivated(case: Case) -> None:
    """Raises ValueError if case is closed/deactivated."""
    current = case.status.value if hasattr(case.status, "value") else str(case.status)
    if current in _TERMINAL_CLOSE_STATUSES:
        raise ValueError("Case is closed — no new sessions can be created")


def get_status_report(
    db: Session,
    *,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    case_manager_id: Optional[int] = None,
    service_type: Optional[str] = None,
    ageing_gt_days: Optional[int] = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """Paginated client status report data."""
    from app.models.assignment import CaseAssignment
    from app.models.child import Child

    stmt = select(Case).join(Child, Case.child_id == Child.id)

    if status:
        try:
            stmt = stmt.where(Case.status == CaseStatus(status.upper()))
        except ValueError:
            pass
    if from_date:
        stmt = stmt.where(Case.status_effective_date >= from_date)
    if to_date:
        stmt = stmt.where(Case.status_effective_date <= to_date)
    if case_manager_id:
        stmt = stmt.where(Case.case_manager_user_id == case_manager_id)
    if service_type:
        stmt = stmt.where(Case.service_type.ilike(f"%{service_type}%"))

    total = db.scalar(select(sa_func.count()).select_from(stmt.subquery()))
    offset = (page - 1) * page_size
    cases = db.scalars(stmt.order_by(Case.updated_at.desc()).offset(offset).limit(page_size)).all()

    today = date.today()
    items = []
    for c in cases:
        # Get active therapist assignment
        active_assign = db.scalars(
            select(CaseAssignment)
            .where(
                CaseAssignment.case_id == c.id,
                CaseAssignment.status == "ACTIVE",
            )
            .limit(1)
        ).first()
        therapist_name = None
        if active_assign:
            therapist = db.get(User, active_assign.therapist_user_id)
            therapist_name = therapist.full_name if therapist else None

        cm = db.get(User, c.case_manager_user_id) if c.case_manager_user_id else None
        changed_by = db.get(User, c.status_changed_by_user_id) if c.status_changed_by_user_id else None
        current_status = c.status.value if hasattr(c.status, "value") else str(c.status)

        ageing_days = None
        if c.status_effective_date and current_status in (
            CaseStatus.SUSPENDED.value,
            CaseStatus.PENDING_REPLACEMENT.value,
        ):
            ageing_days = (today - c.status_effective_date).days

        if ageing_gt_days is not None and (ageing_days is None or ageing_days <= ageing_gt_days):
            continue

        items.append({
            "caseId": c.id,
            "caseCode": c.case_code,
            "clientName": c.child.full_name if c.child else None,
            "serviceType": c.service_type,
            "currentStatus": current_status,
            "statusEffectiveDate": c.status_effective_date.isoformat() if c.status_effective_date else None,
            "statusReason": c.status_reason,
            "lastChangedAt": c.updated_at.isoformat() if c.updated_at else None,
            "caseManagerName": cm.full_name if cm else None,
            "therapistName": therapist_name,
            "ageingDays": ageing_days,
            "lastUpdatedBy": changed_by.full_name if changed_by else None,
        })

    pages = max(1, -(-total // page_size))  # ceiling division
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}
