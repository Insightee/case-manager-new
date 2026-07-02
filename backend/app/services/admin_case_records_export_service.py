"""CSV export of all case records for the admin Cases board."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.user import User
from app.services.admin_scope_service import apply_case_scope
from app.services.leave_policy_service import _leave_case_ids
from app.services.leave_service import leave_day_count

MAX_EXPORT_ROWS = 5000

CASE_RECORDS_HEADERS: list[tuple[str, str]] = [
    ("Case Id", "case_code"),
    ("Client id", "external_client_id"),
    ("Client name", "client_name"),
    ("Therapist id", "therapist_external_id"),
    ("Therapist", "therapist_name"),
    ("Case manager", "case_manager_name"),
    ("Case create date", "case_create_date"),
    ("No of session logs", "session_log_count"),
    ("Session logs due", "session_logs_due"),
    ("Approval pending", "approval_pending"),
    ("Leaves taken", "leaves_taken"),
    ("Approved child absence", "approved_child_absence"),
]


def _missing_logs_by_case(db: Session, case_ids: list[int]) -> dict[int, int]:
    if not case_ids:
        return {}
    return dict(
        db.execute(
            select(TherapySession.case_id, func.count())
            .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id.in_(case_ids),
                TherapySession.status == SessionStatus.COMPLETED,
                DailyLog.id.is_(None),
            )
            .group_by(TherapySession.case_id)
        ).all()
    )


def _session_log_counts_by_case(db: Session, case_ids: list[int]) -> dict[int, int]:
    if not case_ids:
        return {}
    return dict(
        db.execute(
            select(TherapySession.case_id, func.count())
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(TherapySession.case_id.in_(case_ids))
            .group_by(TherapySession.case_id)
        ).all()
    )


def _pending_approval_by_case(db: Session, case_ids: list[int]) -> dict[int, int]:
    if not case_ids:
        return {}
    return dict(
        db.execute(
            select(TherapySession.case_id, func.count())
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id.in_(case_ids),
                DailyLog.approval_status == LogApprovalStatus.PENDING.value,
            )
            .group_by(TherapySession.case_id)
        ).all()
    )


def _approved_child_absence_by_case(db: Session, case_ids: list[int]) -> dict[int, int]:
    if not case_ids:
        return {}
    return dict(
        db.execute(
            select(SessionAbsenceRequest.case_id, func.count())
            .where(
                SessionAbsenceRequest.case_id.in_(case_ids),
                SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
                SessionAbsenceRequest.status == SessionAbsenceStatus.APPROVED,
            )
            .group_by(SessionAbsenceRequest.case_id)
        ).all()
    )


def _leave_days_by_case(db: Session, case_ids: set[int]) -> dict[int, int]:
    if not case_ids:
        return {}
    counts: dict[int, int] = defaultdict(int)
    leaves = db.scalars(
        select(TherapistLeave).where(TherapistLeave.status == LeaveStatus.APPROVED)
    ).all()
    for leave in leaves:
        linked = _leave_case_ids(leave)
        if not linked:
            continue
        days = leave_day_count(leave.start_date, leave.end_date)
        for cid in linked:
            if cid in case_ids:
                counts[cid] += days
    return dict(counts)


def build_case_records_rows(db: Session, user: User) -> list[dict[str, Any]]:
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    stmt = apply_case_scope(stmt, user)
    cases = list(db.scalars(stmt).all())
    if not cases:
        return []

    case_ids = [c.id for c in cases]
    case_id_set = set(case_ids)

    active_assignments = db.execute(
        select(
            CaseAssignment.case_id,
            CaseAssignment.therapist_user_id,
            User.full_name,
            User.external_employee_id,
        )
        .join(User, User.id == CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.case_id.in_(case_ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    assign_by_case: dict[int, tuple] = {row.case_id: row for row in active_assignments}

    cm_ids = {c.case_manager_user_id for c in cases if c.case_manager_user_id}
    cm_names: dict[int, str] = {}
    if cm_ids:
        cm_names = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(cm_ids))).all())

    log_counts = _session_log_counts_by_case(db, case_ids)
    missing_logs = _missing_logs_by_case(db, case_ids)
    pending_approval = _pending_approval_by_case(db, case_ids)
    child_absence = _approved_child_absence_by_case(db, case_ids)
    leave_days = _leave_days_by_case(db, case_id_set)

    rows: list[dict[str, Any]] = []
    for case in cases:
        child = case.child
        assign = assign_by_case.get(case.id)
        cm_id = case.case_manager_user_id
        created = case.created_at.date().isoformat() if case.created_at else ""

        rows.append(
            {
                "case_code": case.case_code,
                "external_client_id": (child.external_client_id if child else "") or "",
                "client_name": child.full_name if child else "",
                "therapist_external_id": (assign.external_employee_id if assign else "") or "",
                "therapist_name": assign.full_name if assign else "",
                "case_manager_name": cm_names.get(cm_id, "") if cm_id else "",
                "case_create_date": created,
                "session_log_count": int(log_counts.get(case.id, 0)),
                "session_logs_due": int(missing_logs.get(case.id, 0)),
                "approval_pending": int(pending_approval.get(case.id, 0)),
                "leaves_taken": int(leave_days.get(case.id, 0)),
                "approved_child_absence": int(child_absence.get(case.id, 0)),
            }
        )
    return rows


def export_case_records_csv(db: Session, user: User) -> str:
    rows = build_case_records_rows(db, user)
    if len(rows) > MAX_EXPORT_ROWS:
        raise ValueError(
            f"Export has {len(rows)} rows (max {MAX_EXPORT_ROWS}). Contact support for a bulk extract."
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([header for header, _ in CASE_RECORDS_HEADERS])
    for row in rows:
        writer.writerow([row.get(key, "") for _, key in CASE_RECORDS_HEADERS])
    return output.getvalue()
