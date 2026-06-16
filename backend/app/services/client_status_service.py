from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus
from app.models.case_client_status_audit import CaseClientStatusAudit
from app.models.user import User

# Allowed admin-direct transitions
ADMIN_ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    CaseStatus.PENDING_ALLOTMENT.value: [CaseStatus.ACTIVE.value],
    CaseStatus.ACTIVE.value: [
        CaseStatus.SUSPENDED.value,
        CaseStatus.PENDING_REPLACEMENT.value,
        CaseStatus.DEACTIVATED.value,
    ],
    CaseStatus.SUSPENDED.value: [
        CaseStatus.ACTIVE.value,
        CaseStatus.DEACTIVATED.value,
    ],
    CaseStatus.PENDING_REPLACEMENT.value: [
        CaseStatus.ACTIVE.value,
        CaseStatus.DEACTIVATED.value,
    ],
    CaseStatus.DEACTIVATED.value: [],  # terminal
    CaseStatus.CLOSED.value: [],       # legacy terminal
}

AGEING_WARN_DAYS = 7  # configurable threshold for highlighting


def _cancel_future_bookings(db: Session, case_id: int) -> None:
    """Reuse the existing booking cancellation logic."""
    from app.services.case_status_request_service import _cancel_future_bookings as _cfb
    _cfb(db, case_id)


def change_client_status(
    db: Session,
    case: Case,
    user: User,
    new_status: str,
    effective_date: date,
    reason: str,
    internal_notes: Optional[str] = None,
) -> CaseClientStatusAudit:
    """Admin-direct status change with full audit trail. Caller must commit."""
    current_status = case.status.value if hasattr(case.status, "value") else str(case.status)
    new_status_upper = new_status.upper()

    # Validate transition
    allowed = ADMIN_ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status_upper not in allowed:
        raise ValueError(
            f"Cannot transition from {current_status} to {new_status_upper}. "
            f"Allowed: {allowed or ['none (terminal state)']}"
        )

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
        CaseStatus.DEACTIVATED.value,
    ):
        _cancel_future_bookings(db, case.id)

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
    """Raises ValueError if case is deactivated."""
    current = case.status.value if hasattr(case.status, "value") else str(case.status)
    if current == CaseStatus.DEACTIVATED.value:
        raise ValueError("Case is deactivated — no new sessions can be created")


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
