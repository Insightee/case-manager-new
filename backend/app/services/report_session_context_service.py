from __future__ import annotations

import io
from datetime import date
from typing import Optional

from sqlalchemy import extract, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import case_scope_check, user_has_permission
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.report import MonthlyReport
from app.models.session import Session as TherapySession
from app.services import case_service


def _parse_month(month_str: str) -> tuple[int, int] | None:
    """Parse 'May 2026' or '2026-05' into (year, month)."""
    from datetime import datetime

    s = (month_str or "").strip()
    if not s:
        return None
    if len(s) >= 7 and s[4] == "-":
        try:
            y, m = int(s[:4]), int(s[5:7])
            if 1 <= m <= 12:
                return y, m
        except ValueError:
            pass
    for fmt in ("%B %Y", "%b %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.year, dt.month
        except ValueError:
            continue
    return None


def session_context_for_monthly_report(db: Session, user, report: MonthlyReport) -> list[dict]:
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        return []
    ym = _parse_month(report.month)
    if not ym:
        return []
    year, month = ym
    stmt = (
        select(DailyLog)
        .join(TherapySession)
        .where(
            TherapySession.case_id == report.case_id,
            extract("year", TherapySession.scheduled_date) == year,
            extract("month", TherapySession.scheduled_date) == month,
            DailyLog.submitted_at.isnot(None),
            DailyLog.approval_status == LogApprovalStatus.APPROVED,
        )
        .options(selectinload(DailyLog.session))
        .order_by(TherapySession.scheduled_date.asc())
    )
    logs = db.scalars(stmt).all()
    out = []
    for log in logs:
        s = log.session
        if not s:
            continue
        out.append(
            {
                "log_id": log.id,
                "scheduled_date": s.scheduled_date.isoformat() if s.scheduled_date else None,
                "start_time": s.start_time.isoformat() if s.start_time else None,
                "end_time": s.end_time.isoformat() if s.end_time else None,
                "attendance_status": log.attendance_status,
                "activities_done": log.activities_done,
                "goals_addressed": log.goals_addressed,
                "follow_ups": log.follow_ups,
                "parent_notes": log.parent_notes,
                "session_notes": log.session_notes,
            }
        )
    return out


def export_session_logs_csv(
    db: Session,
    user,
    *,
    case_id: int,
    month: Optional[str] = None,
    year: Optional[int] = None,
    month_num: Optional[int] = None,
) -> str:
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise ValueError("Case not found")
    if user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        from app.models.assignment import CaseAssignment, CaseAssignmentStatus
        from sqlalchemy import select as sa_select

        active = db.scalars(
            sa_select(CaseAssignment).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.therapist_user_id == user.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        if not active:
            raise ValueError("Case not found")

    if month:
        parsed = _parse_month(month)
        if parsed:
            year, month_num = parsed

    stmt = (
        select(DailyLog)
        .join(TherapySession)
        .where(
            TherapySession.case_id == case_id,
            DailyLog.submitted_at.isnot(None),
            DailyLog.approval_status == LogApprovalStatus.APPROVED,
        )
        .options(selectinload(DailyLog.session))
        .order_by(TherapySession.scheduled_date.asc())
    )
    if year is not None:
        stmt = stmt.where(extract("year", TherapySession.scheduled_date) == year)
    if month_num is not None:
        stmt = stmt.where(extract("month", TherapySession.scheduled_date) == month_num)
    if user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        stmt = stmt.where(TherapySession.therapist_user_id == user.id)

    logs = db.scalars(stmt).all()
    import csv

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "log_id", "session_id", "case_id", "scheduled_date", "attendance",
        "activities", "goals", "follow_ups", "parent_notes", "session_notes",
    ])
    for log in logs:
        s = log.session
        if not s:
            continue
        writer.writerow([
            log.id,
            log.session_id,
            case_id,
            s.scheduled_date.isoformat() if s.scheduled_date else "",
            log.attendance_status,
            log.activities_done or "",
            log.goals_addressed or "",
            log.follow_ups or "",
            log.parent_notes or "",
            log.session_notes or "",
        ])
    return output.getvalue()
