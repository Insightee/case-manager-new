"""Shared helpers for operational report exports."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.user import User
from app.services.admin_scope_service import apply_case_scope
from app.services import case_service

IST = ZoneInfo("Asia/Kolkata")
MAX_EXPORT_ROWS = 5000
INACTIVE_DAYS_THRESHOLD = 7


def default_export_month() -> str:
    return datetime.now(IST).strftime("%Y-%m")


def normalize_month(value: str | None) -> str:
    raw = (value or default_export_month()).strip()
    if len(raw) >= 7 and raw[4] == "-":
        return raw[:7]
    return default_export_month()


def month_bounds(ym: str) -> tuple[date, date]:
    year_s, month_s = ym.split("-")[:2]
    y, m = int(year_s), int(month_s)
    return date(y, m, 1), date(y, m, monthrange(y, m)[1])


def calendar_days_in_month(ym: str) -> int:
    year_s, month_s = ym.split("-")[:2]
    return monthrange(int(year_s), int(month_s))[1]


def month_long_label(ym: str) -> str:
    start, _ = month_bounds(ym)
    return start.strftime("%B %Y")


def export_case_id(case: Case | None) -> str:
    if not case:
        return ""
    ref = (case.external_case_ref or "").strip()
    if ref:
        return ref
    return (case.case_code or "").strip()


def export_therapist_id(user: User | None) -> str:
    if not user:
        return ""
    return (user.external_employee_id or "").strip()


def user_display_name(user: User | None) -> str:
    if not user:
        return ""
    return (user.full_name or user.email or "").strip()


def enum_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def scoped_cases(
    db: Session,
    user: User | None,
    *,
    product_module: str | None = None,
    case_manager_user_id: int | None = None,
    active_only: bool = False,
) -> list[Case]:
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    if user is not None:
        stmt = apply_case_scope(stmt, user)
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    if case_manager_user_id:
        stmt = stmt.where(Case.case_manager_user_id == case_manager_user_id)
    if active_only:
        stmt = stmt.where(Case.status == CaseStatus.ACTIVE)
    return list(db.scalars(stmt).all())


def active_assignment(db: Session, case_id: int) -> CaseAssignment | None:
    return db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.id.desc())
        .limit(1)
    ).first()


def assignment_therapist(db: Session, assignment: CaseAssignment | None) -> User | None:
    if not assignment:
        return None
    return db.get(User, assignment.therapist_user_id)


def case_manager(db: Session, case: Case) -> User | None:
    if not case.case_manager_user_id:
        return None
    return db.get(User, case.case_manager_user_id)


def mentor_for_therapist(db: Session, therapist_user_id: int | None) -> User | None:
    if not therapist_user_id:
        return None
    from app.models.therapist_profile import TherapistProfile

    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id)
    ).first()
    if not profile or not profile.mentor_user_id:
        return None
    return db.get(User, profile.mentor_user_id)


def last_completed_session_date(db: Session, case_id: int) -> date | None:
    from app.models.session import Session as TherapySession
    from app.models.session import SessionStatus

    return db.scalar(
        select(TherapySession.scheduled_date)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.status == SessionStatus.COMPLETED,
        )
        .order_by(TherapySession.scheduled_date.desc())
        .limit(1)
    )


def days_since(date_value: date | None, *, as_of: date | None = None) -> int | None:
    if not date_value:
        return None
    ref = as_of or date.today()
    return max((ref - date_value).days, 0)


def parse_iso_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return fallback


def leave_days_in_month(db: Session, therapist_user_id: int, ym: str) -> dict[str, int]:
    """Paid/unpaid leave days overlapping the calendar month."""
    from app.models.leave import LeaveStatus, TherapistLeave
    from app.services import leave_service
    from app.services.leave_policy_service import _paid_unpaid_for_leave

    start, end = month_bounds(ym)
    year = int(ym.split("-")[0])
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.status == LeaveStatus.APPROVED,
            TherapistLeave.start_date <= end,
            TherapistLeave.end_date >= start,
        )
    ).all()
    paid = unpaid = carry = 0
    for lv in leaves:
        p, u = _paid_unpaid_for_leave(db, lv, year)
        overlap_start = max(lv.start_date, start)
        overlap_end = min(lv.end_date, end)
        if overlap_end < overlap_start:
            continue
        total = leave_service.leave_day_count(overlap_start, overlap_end)
        if total <= 0:
            continue
        full = leave_service.leave_day_count(lv.start_date, lv.end_date) or 1
        ratio = total / full
        paid += round(p * ratio)
        unpaid += round(u * ratio)
    return {"paid": paid, "unpaid": unpaid, "carry_forward": carry}


def is_shadow_case(case: Case | None) -> bool:
    return "shadow" in ((case.product_module if case else "") or "").lower()


def is_homecare_case(case: Case | None) -> bool:
    mod = ((case.product_module if case else "") or "").lower()
    return "homecare" in mod


def shadow_per_session_day_rate(monthly_fixed_pay: float | None, scheduled_sessions: int) -> float:
    """Monthly fixed pay divided by scheduled sessions in the month."""
    if not monthly_fixed_pay or scheduled_sessions <= 0:
        return 0.0
    return round(float(monthly_fixed_pay) / scheduled_sessions, 2)


def shadow_leave_deduction_estimate(
    monthly_fixed_pay: float | None, scheduled_sessions: int, unpaid_leave_days: int
) -> float:
    rate = shadow_per_session_day_rate(monthly_fixed_pay, scheduled_sessions)
    if rate <= 0 or unpaid_leave_days <= 0:
        return 0.0
    return round(rate * unpaid_leave_days, 2)


def monthly_report_submitted(db: Session, case_id: int, ym: str) -> bool:
    from sqlalchemy import or_

    from app.models.report import MonthlyReport, ReportStatus

    long_label = month_long_label(ym)
    row = db.scalars(
        select(MonthlyReport)
        .where(
            MonthlyReport.case_id == case_id,
            or_(MonthlyReport.month.ilike(f"%{ym}%"), MonthlyReport.month.ilike(f"%{long_label}%")),
            MonthlyReport.status.in_(
                [
                    ReportStatus.UNDER_REVIEW,
                    ReportStatus.APPROVED,
                    ReportStatus.PUBLISHED,
                ]
            ),
        )
        .limit(1)
    ).first()
    return row is not None
