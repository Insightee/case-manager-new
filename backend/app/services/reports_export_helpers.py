"""Shared helpers for operational report exports."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.billing_month import default_billing_month, parse_billing_month
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.parent import ParentGuardian, parent_child_link
from app.models.user import User
from app.services.admin_scope_service import apply_case_scope
from app.services import case_service

IST = ZoneInfo("Asia/Kolkata")
MAX_EXPORT_ROWS = 5000
INACTIVE_DAYS_THRESHOLD = 7
THERAPIST_LOG_COMPLIANCE_MIN_AGE_DAYS = 2


def default_export_month() -> str:
    return default_billing_month()


def normalize_month(value: str | None) -> str:
    return parse_billing_month(value)


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


def export_generated_on_stamp() -> str:
    """IST calendar date for download filenames and document titles (YYYY-MM-DD)."""
    return datetime.now(IST).strftime("%Y-%m-%d")


def export_filename_stem(report_key: str, *, generated_on: str | None = None) -> str:
    stamp = generated_on or export_generated_on_stamp()
    return f"{report_key}-{stamp}"


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


def parent_by_child(db: Session, child_ids: set[int]) -> dict[int, dict[str, Any]]:
    """Map child_id → first linked parent {user_id, parent_name, parent_email}."""
    if not child_ids:
        return {}

    rows = db.execute(
        select(
            parent_child_link.c.child_id,
            User.id,
            User.full_name,
            User.email,
        )
        .join(ParentGuardian, ParentGuardian.id == parent_child_link.c.parent_guardian_id)
        .join(User, User.id == ParentGuardian.user_id)
        .where(parent_child_link.c.child_id.in_(child_ids))
        .order_by(parent_child_link.c.child_id, ParentGuardian.id)
    ).all()
    out: dict[int, dict[str, Any]] = {}
    for child_id, user_id, full_name, email in rows:
        if child_id in out:
            continue
        out[child_id] = {
            "user_id": user_id,
            "parent_name": full_name or "",
            "parent_email": email or "",
        }
    return out


def case_people_export_fields(
    case: Case | None,
    *,
    therapist: User | None = None,
    parent_info: dict[str, Any] | None = None,
    include_therapist: bool = True,
) -> dict[str, str]:
    """Standard Case / Child / Parent / Therapist identity columns for HR exports."""
    parent = parent_info or {}
    fields: dict[str, str] = {
        "Case ID": export_case_id(case),
        "Child Name": case_service.case_child_display_name(case) or "",
        "Parent Name": str(parent.get("parent_name") or ""),
    }
    if include_therapist:
        fields["Therapist Name"] = user_display_name(therapist)
        fields["Therapist ID"] = export_therapist_id(therapist)
    return fields


def enum_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def parse_int_list(value: int | str | list[int] | None) -> list[int] | None:
    """Parse a single int, list of ints, or comma-separated string into ints.

    Returns None when empty / unset. Used by HR report and meeting filters so
    ``case_manager_user_id=1,2,3`` (and repeated query values coerced to a list)
    work alongside legacy single-id callers.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        ids = [int(x) for x in value if x is not None and str(x).strip() != ""]
        return ids or None
    raw = str(value).strip()
    if not raw:
        return None
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        ids.append(int(part))
    return ids or None


def apply_case_manager_filter(stmt: Any, column: Any, case_manager_user_id: int | list[int] | None):
    """Filter by one CM id (equality) or many (``IN_``). No-op when unset/empty."""
    if case_manager_user_id is None:
        return stmt
    if isinstance(case_manager_user_id, list):
        ids = [int(i) for i in case_manager_user_id if i is not None]
        if not ids:
            return stmt
        return stmt.where(column.in_(ids))
    return stmt.where(column == case_manager_user_id)


def scoped_cases(
    db: Session,
    user: User | None,
    *,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
    active_only: bool = False,
) -> list[Case]:
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    if user is not None:
        stmt = apply_case_scope(stmt, user)
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    stmt = apply_case_manager_filter(stmt, Case.case_manager_user_id, case_manager_user_id)
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


def cases_by_ids(db: Session, case_ids: set[int] | list[int]) -> dict[int, Case]:
    """Batch-load cases with child for export identity columns."""
    ids = {int(cid) for cid in case_ids if cid is not None}
    if not ids:
        return {}
    rows = db.scalars(
        select(Case).options(selectinload(Case.child)).where(Case.id.in_(ids))
    ).all()
    return {case.id: case for case in rows}


def active_therapists_by_case(
    db: Session, case_ids: set[int] | list[int]
) -> dict[int, User]:
    """Map case_id → active therapist user (latest active assignment wins)."""
    ids = {int(cid) for cid in case_ids if cid is not None}
    if not ids:
        return {}
    assign_rows = db.execute(
        select(CaseAssignment.case_id, CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.case_id.in_(ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.id.desc())
    ).all()
    therapist_id_by_case: dict[int, int] = {}
    for case_id, therapist_user_id in assign_rows:
        if case_id not in therapist_id_by_case:
            therapist_id_by_case[case_id] = int(therapist_user_id)
    if not therapist_id_by_case:
        return {}
    users = {
        u.id: u
        for u in db.scalars(
            select(User).where(User.id.in_(set(therapist_id_by_case.values())))
        ).all()
    }
    return {
        case_id: users[tid]
        for case_id, tid in therapist_id_by_case.items()
        if tid in users
    }


def clip_assignment_to_month(
    assign_start: date,
    assign_end: date | None,
    month_start: date,
    month_end: date,
) -> tuple[date, date] | None:
    """Inclusive clip of an assignment window into a month. None if no overlap."""
    end = assign_end if assign_end is not None else month_end
    start = max(assign_start, month_start)
    end = min(end, month_end)
    if start > end:
        return None
    return start, end


def assignment_segments_for_month(
    db: Session,
    case_ids: list[int] | set[int],
    month_start: date,
    month_end: date,
) -> dict[int, list[dict[str, Any]]]:
    """
    Case → assignment slices overlapping the month (ACTIVE/ENDED/TRANSFERRED).

    Each segment: assignment, therapist_user_id, start, end (clipped inclusive).
    Cases with no overlapping history get no entry (caller may fall back).
    """
    ids = [int(cid) for cid in case_ids if cid is not None]
    out: dict[int, list[dict[str, Any]]] = {cid: [] for cid in ids}
    if not ids:
        return {}

    rows = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id.in_(ids),
            CaseAssignment.status.in_(
                [
                    CaseAssignmentStatus.ACTIVE,
                    CaseAssignmentStatus.ENDED,
                    CaseAssignmentStatus.TRANSFERRED,
                ]
            ),
            CaseAssignment.start_date <= month_end,
        )
        .order_by(CaseAssignment.case_id, CaseAssignment.start_date, CaseAssignment.id)
    ).all()

    for assign in rows:
        if assign.end_date is not None and assign.end_date < month_start:
            continue
        clipped = clip_assignment_to_month(
            assign.start_date, assign.end_date, month_start, month_end
        )
        if not clipped:
            continue
        out.setdefault(assign.case_id, []).append(
            {
                "assignment": assign,
                "therapist_user_id": assign.therapist_user_id,
                "start": clipped[0],
                "end": clipped[1],
            }
        )
    return {cid: segs for cid, segs in out.items() if segs}


def billing_snapshot_report_columns(snapshot: dict | None) -> dict[str, str]:
    """Flatten locked assignment billing snapshot for HR export rows.

    Always presents lumpsum INR pay — never legacy PERCENTAGE / \"share\" wording.
    """
    if not snapshot:
        return {
            "Previous Billing Type": "",
            "Previous Client Rate": "",
            "Previous Package Amount": "",
            "Previous Compensation Mode": "",
            "Previous Therapist Pay": "",
        }
    billing_type = snapshot.get("billing_type") or ""
    client_rate = ""
    if billing_type == "PER_SESSION":
        rate = snapshot.get("client_rate_per_session_inr")
        client_rate = f"₹{rate}/session" if rate is not None else ""
    elif billing_type == "MONTHLY_FIXED":
        rate = snapshot.get("client_monthly_rate_inr")
        client_rate = f"₹{rate}/month" if rate is not None else ""
    elif billing_type == "PACKAGE":
        count = snapshot.get("package_session_count")
        amount = snapshot.get("package_amount_inr")
        client_rate = f"₹{amount} / {count} sessions" if amount is not None and count else ""

    # Prefer fixed lump; fall back to legacy share column (already INR). Never label as %.
    pay = snapshot.get("therapist_fixed_pay_inr")
    if pay is None or float(pay or 0) <= 0:
        pay = snapshot.get("pay_share_amount_inr")
    therapist_pay = f"₹{pay} lumpsum" if pay is not None and float(pay or 0) > 0 else ""

    raw_mode = (snapshot.get("compensation_mode") or "").strip()
    if raw_mode in ("", "PERCENTAGE"):
        comp_mode_label = "FIXED LUMP" if therapist_pay else ""
    else:
        comp_mode_label = raw_mode.replace("_", " ")

    package_amount = ""
    if billing_type == "PACKAGE" and snapshot.get("package_amount_inr") is not None:
        package_amount = str(snapshot.get("package_amount_inr"))

    return {
        "Previous Billing Type": billing_type.replace("_", " "),
        "Previous Client Rate": client_rate,
        "Previous Package Amount": package_amount,
        "Previous Compensation Mode": comp_mode_label,
        "Previous Therapist Pay": therapist_pay,
    }


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


def leave_applies_to_case(leave: Any, case_id: int) -> bool:
    """True when leave was recorded against a specific case (not therapist-wide)."""
    if not leave.case_id and not leave.case_ids:
        return False
    if leave.case_id == case_id:
        return True
    if leave.case_ids and case_id in leave.case_ids:
        return True
    return False


def _leave_days_overlap_month(
    db: Session,
    leaves: list[TherapistLeave],
    ym: str,
    *,
    case_id: int | None = None,
) -> dict[str, int]:
    from app.services import leave_dates_service as leave_dates
    from app.services.leave_policy_service import (
        allocations_for_leave,
        month_paid_unpaid_from_allocations,
    )

    start, end = month_bounds(ym)
    paid = unpaid = 0
    for lv in leaves:
        allocations = allocations_for_leave(db, lv)
        if case_id is not None:
            case_days = set(leave_dates.billable_leave_dates(db, lv, case_id=case_id))
            allocations = [item for item in allocations if item.day in case_days]
        month_paid, month_unpaid = month_paid_unpaid_from_allocations(
            allocations,
            start,
            end,
        )
        paid += month_paid
        unpaid += month_unpaid
    return {"paid": paid, "unpaid": unpaid, "carry_forward": 0}


def leave_days_in_month(db: Session, therapist_user_id: int, ym: str) -> dict[str, int]:
    """Paid/unpaid leave days overlapping the calendar month (all therapist leaves)."""
    from app.models.leave import LeaveStatus, TherapistLeave

    start, end = month_bounds(ym)
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.status == LeaveStatus.APPROVED,
            TherapistLeave.start_date <= end,
            TherapistLeave.end_date >= start,
        )
    ).all()
    return _leave_days_overlap_month(db, leaves, ym)


def leave_days_in_month_for_case(
    db: Session,
    therapist_user_id: int,
    case_id: int,
    ym: str,
) -> dict[str, int]:
    """Paid/unpaid leave days for a therapist scoped to one case in the billing month."""
    from app.models.leave import LeaveStatus, TherapistLeave

    start, end = month_bounds(ym)
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.status == LeaveStatus.APPROVED,
            TherapistLeave.start_date <= end,
            TherapistLeave.end_date >= start,
        )
    ).all()
    scoped = [
        lv
        for lv in leaves
        if leave_applies_to_case(lv, case_id) or (not lv.case_id and not lv.case_ids)
    ]
    return _leave_days_overlap_month(db, scoped, ym, case_id=case_id)


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
