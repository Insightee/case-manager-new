"""One-time / migration backfill for leave billing_category and service_line."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.therapist_profile import TherapistProfile
from app.services import leave_policy_service as policy

SHADOW = policy.SHADOW_SERVICE_LINE


def infer_service_line(db: Session, therapist_user_id: int) -> str:
    rows = db.scalars(
        select(CaseAssignment.case_id).where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    if not rows:
        return "homecare"
    case_ids = list(rows)
    cases = db.scalars(select(Case).where(Case.id.in_(case_ids))).all()
    modules = [c.product_module for c in cases if c.product_module]
    if any(m == SHADOW for m in modules):
        return SHADOW
    return modules[0] if modules else "homecare"


def classify_legacy_leave(
    leave: TherapistLeave,
    *,
    service_line: str,
    paid_month_keys: set[tuple[int, int]],
) -> LeaveBillingCategory:
    if leave.leave_type == LeaveType.UNPAID:
        return LeaveBillingCategory.UNPAID
    if service_line != SHADOW:
        return LeaveBillingCategory.UNPAID
    month_key = (leave.start_date.year, leave.start_date.month)
    if month_key not in paid_month_keys:
        paid_month_keys.add(month_key)
        return LeaveBillingCategory.PAID
    return LeaveBillingCategory.CARRY_FORWARD


def backfill_approved_leaves(db: Session, *, year: int | None = None) -> int:
    """Set service_line and billing_category on approved leaves; init profile backfill year."""
    year = year or date.today().year
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.status == LeaveStatus.APPROVED,
            TherapistLeave.start_date <= year_end,
            TherapistLeave.end_date >= year_start,
        )
    ).all()

    by_therapist: dict[int, list[TherapistLeave]] = defaultdict(list)
    for lv in leaves:
        by_therapist[lv.therapist_user_id].append(lv)

    updated = 0
    for therapist_id, therapist_leaves in by_therapist.items():
        service_line = infer_service_line(db, therapist_id)
        paid_month_keys: set[tuple[int, int]] = set()
        therapist_leaves.sort(key=lambda x: (x.start_date, x.id))
        for lv in therapist_leaves:
            if lv.billing_category is not None and lv.service_line:
                continue
            lv.service_line = lv.service_line or service_line
            lv.billing_category = classify_legacy_leave(
                lv, service_line=lv.service_line, paid_month_keys=paid_month_keys
            )
            updated += 1

    profiles = db.scalars(select(TherapistProfile)).all()
    for p in profiles:
        if p.leave_balance_year is None:
            p.leave_balance_year = year
        if p.leave_paid_days_backfill is None:
            p.leave_paid_days_backfill = 0
        if p.leave_carry_forward_days_backfill is None:
            p.leave_carry_forward_days_backfill = 0

    return updated


def run_backfill_on_connection(connection) -> None:
    from sqlalchemy.orm import Session

    session = Session(bind=connection)
    try:
        backfill_approved_leaves(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
