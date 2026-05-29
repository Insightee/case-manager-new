"""Shared queries for monthly-report session log context and compilation."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import extract, select
from sqlalchemy.orm import Session, selectinload

from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.report import MonthlyReport
from app.models.session import Session as TherapySession

_COMPILE_STATUSES = (LogApprovalStatus.PENDING, LogApprovalStatus.APPROVED)


def parse_report_month(month_str: str) -> tuple[int, int] | None:
    """Parse 'May 2026' or '2026-05' into (year, month)."""
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


def submitted_logs_for_report_month(
    db: Session,
    report: MonthlyReport,
    *,
    approval_statuses: tuple[LogApprovalStatus, ...] = _COMPILE_STATUSES,
) -> list[DailyLog]:
    ym = parse_report_month(report.month)
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
            DailyLog.approval_status.in_(approval_statuses),
        )
        .options(selectinload(DailyLog.session))
        .order_by(TherapySession.scheduled_date.asc())
    )
    return list(db.scalars(stmt).all())


def log_to_context_dict(log: DailyLog) -> dict:
    s = log.session
    status = log.approval_status
    status_val = status.value if hasattr(status, "value") else str(status)
    return {
        "log_id": log.id,
        "scheduled_date": s.scheduled_date.isoformat() if s and s.scheduled_date else None,
        "start_time": s.start_time.isoformat() if s and s.start_time else None,
        "end_time": s.end_time.isoformat() if s and s.end_time else None,
        "attendance_status": log.attendance_status,
        "approval_status": status_val,
        "activities_done": log.activities_done,
        "goals_addressed": log.goals_addressed,
        "follow_ups": log.follow_ups,
        "parent_notes": log.parent_notes,
        "session_notes": log.session_notes,
    }
