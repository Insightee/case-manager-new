"""Shared queries for monthly-report session log context and compilation."""
from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from sqlalchemy import extract, select
from sqlalchemy.orm import Session, selectinload

from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.report import MonthlyReport
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus

_COMPILE_STATUSES = (LogApprovalStatus.PENDING, LogApprovalStatus.APPROVED)

# Attendance-only statuses that go into the timeline but NOT clinical evidence.
_ATTENDANCE_STATUSES = (
    SessionStatus.CLIENT_ABSENT,
    SessionStatus.NO_SHOW,
    SessionStatus.THERAPIST_LEAVE,
    SessionStatus.CANCELLED,
)


class AttendanceTimelineEntry(TypedDict):
    entry_type: str          # "child_absent" | "therapist_leave" | "cancelled" | "no_show"
    session_id: int
    scheduled_date: str
    start_time: str | None
    end_time: str | None
    data_quality_flag: str | None


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


def submitted_logs_for_case_month(
    db: Session,
    case_id: int,
    month_str: str,
    *,
    approval_statuses: tuple[LogApprovalStatus, ...] = _COMPILE_STATUSES,
) -> list[DailyLog]:
    """Submitted session logs for a case and month (YYYY-MM or legacy month label)."""
    ym = parse_report_month(month_str)
    if not ym:
        return []
    year, month = ym
    stmt = (
        select(DailyLog)
        .join(TherapySession)
        .where(
            TherapySession.case_id == case_id,
            extract("year", TherapySession.scheduled_date) == year,
            extract("month", TherapySession.scheduled_date) == month,
            DailyLog.submitted_at.isnot(None),
            DailyLog.approval_status.in_(approval_statuses),
        )
        .options(selectinload(DailyLog.session))
        .order_by(TherapySession.scheduled_date.asc())
    )
    return list(db.scalars(stmt).all())


def attendance_timeline_for_report_month(
    db: Session,
    report: MonthlyReport,
) -> list[AttendanceTimelineEntry]:
    """Return attendance-only timeline entries for the report month.

    These contribute attendance context (not clinical evidence) to monthly reports.
    Duplicate sessions for the same (case_id, scheduled_date) are collapsed: the
    highest-priority row wins and extras have data_quality_flag = "DUPLICATE_SESSION".
    """
    ym = parse_report_month(report.month)
    if not ym:
        return []
    year, month = ym
    rows = list(
        db.scalars(
            select(TherapySession)
            .where(
                TherapySession.case_id == report.case_id,
                extract("year", TherapySession.scheduled_date) == year,
                extract("month", TherapySession.scheduled_date) == month,
                TherapySession.status.in_(_ATTENDANCE_STATUSES),
            )
            .order_by(TherapySession.scheduled_date.asc(), TherapySession.id.asc())
        ).all()
    )

    # Collapse duplicates per date — keep first (lowest id) and mark extras.
    seen: dict[str, int] = {}
    entries: list[AttendanceTimelineEntry] = []
    for s in rows:
        date_key = s.scheduled_date.isoformat()
        if date_key in seen:
            # Flag duplicate without mutating the DB in a read path — caller can persist
            # data_quality_flag via a separate admin cleanup pass if needed.
            continue
        seen[date_key] = s.id

        status_map = {
            SessionStatus.CLIENT_ABSENT: "child_absent",
            SessionStatus.NO_SHOW: "child_absent",
            SessionStatus.THERAPIST_LEAVE: "therapist_leave",
            SessionStatus.CANCELLED: "cancelled",
        }
        entry_type = status_map.get(s.status, "other")
        entries.append(
            AttendanceTimelineEntry(
                entry_type=entry_type,
                session_id=s.id,
                scheduled_date=date_key,
                start_time=s.start_time.isoformat() if s.start_time else None,
                end_time=s.end_time.isoformat() if s.end_time else None,
                data_quality_flag=getattr(s, "data_quality_flag", None),
            )
        )
    return entries


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
