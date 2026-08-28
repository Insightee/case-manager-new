"""Case-centric filtered session log Excel export."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.session_times import effective_session_datetimes
from app.core.timezone import IST, ensure_utc_aware
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services.export_document_service import export_meta, xlsx_footer_rows, xlsx_preamble_rows
from app.services.reports_export_helpers import parent_by_child, case_people_export_fields

Audience = Literal["staff", "parent"]

ONGOING_SESSION_STATUSES = {SessionStatus.SCHEDULED.value, SessionStatus.IN_PROGRESS.value}
CHILD_LEAVE_ATTENDANCE = {"CLIENT_ABSENT", "CLIENT_LEAVE"}

_STAFF_CONTENT_COLUMNS = (
    ("activities_done", "What you did today"),
    ("goals_addressed", "Goals worked on"),
    ("parent_notes", "Update for family"),
    ("session_notes", "Session notes (internal)"),
    ("observations", "Clinical observations"),
    ("follow_ups", "Follow-ups"),
    ("late_reason", "Late reason"),
)

_PARENT_CONTENT_COLUMNS = (
    ("parent_notes", "Update for family"),
    ("activities_done", "What we did today"),
    ("goals_addressed", "Goals worked on"),
    ("follow_ups", "What's next"),
)


@dataclass
class ExportRow:
    scheduled_date: date | None
    time_label: str
    therapist_name: str
    status_label: str
    log: DailyLog | None


def _session_date_iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def _approval_value(log: DailyLog | None) -> str:
    if not log:
        return ""
    status = log.approval_status
    if hasattr(status, "value"):
        status = status.value
    return str(status or "").upper()


def _fmt_ist_range(start, end) -> str:
    if not start or not end:
        return ""
    start_ist = ensure_utc_aware(start).astimezone(IST)
    end_ist = ensure_utc_aware(end).astimezone(IST)
    start_label = start_ist.strftime("%I:%M %p").lstrip("0")
    end_label = end_ist.strftime("%I:%M %p").lstrip("0")
    return f"{start_label} – {end_label} IST"


def _fmt_clock(value) -> str:
    if value is None:
        return ""
    raw = str(value)
    match = re.match(r"^(\d{1,2}):(\d{2})", raw)
    if not match:
        return raw[:5]
    hour = int(match.group(1))
    minute = match.group(2)
    period = "PM" if hour >= 12 else "AM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute} {period}"


def _session_time_label(session: TherapySession | None, log: DailyLog | None) -> str:
    if not session:
        return ""
    start, end = effective_session_datetimes(session, log)
    clock = _fmt_ist_range(start, end)
    if clock:
        return clock
    if session.start_time and session.end_time:
        return f"{_fmt_clock(session.start_time)} – {_fmt_clock(session.end_time)}"
    return ""


def _session_has_time_edit(session: TherapySession | None, log: DailyLog | None) -> bool:
    if not session:
        return False
    if bool(getattr(session, "actual_times_edited", False)):
        return True
    if log and _approval_value(log) == LogApprovalStatus.APPROVED.value:
        edited_start = getattr(session, "edited_start_at", None)
        edited_end = getattr(session, "edited_end_at", None)
        return edited_start is not None and edited_end is not None
    return False


def _is_child_on_leave(session: TherapySession | None, log: DailyLog | None) -> bool:
    session_status = str(session.status.value if session and hasattr(session.status, "value") else session.status or "").upper()
    attendance = (log.attendance_status or "").upper() if log else ""
    return session_status == SessionStatus.CLIENT_ABSENT.value or attendance in CHILD_LEAVE_ATTENDANCE


def _is_therapist_on_leave(session: TherapySession | None, log: DailyLog | None) -> bool:
    session_status = str(session.status.value if session and hasattr(session.status, "value") else session.status or "").upper()
    attendance = (log.attendance_status or "").upper() if log else ""
    return session_status == SessionStatus.THERAPIST_LEAVE.value or attendance == "THERAPIST_LEAVE"


def _staff_status_label(session: TherapySession | None, log: DailyLog | None) -> str:
    if not session and log:
        approval = _approval_value(log)
        if approval == LogApprovalStatus.APPROVED.value:
            return "Approved"
        if approval == LogApprovalStatus.PENDING.value:
            return "Pending review"
        if approval == LogApprovalStatus.REJECTED.value:
            return "Rejected"
        return approval.title() if approval else "Submitted"

    session_status = str(session.status.value if session and hasattr(session.status, "value") else session.status or "").upper()
    approval = _approval_value(log)
    has_log = log is not None
    is_ongoing = session_status in ONGOING_SESSION_STATUSES and not has_log

    if approval == LogApprovalStatus.APPROVED.value:
        return "Approved"
    if approval == LogApprovalStatus.PENDING.value:
        return "Pending review"
    if approval == LogApprovalStatus.REJECTED.value:
        return "Rejected"
    if log and log.resubmitted_at:
        return "Resubmitted"
    if _session_has_time_edit(session, log):
        return "Times edited"
    if is_ongoing:
        return "Ongoing"
    if _is_child_on_leave(session, log):
        return "Child on leave"
    if _is_therapist_on_leave(session, log):
        return "Therapist on leave"
    if session_status == SessionStatus.CANCELLED.value:
        return "Cancelled"
    if not has_log:
        return "No log submitted"
    return approval.title() if approval else "Submitted"


def _parent_status_label(log: DailyLog) -> str:
    approval = _approval_value(log)
    if approval == LogApprovalStatus.APPROVED.value:
        return "Reviewed"
    if approval == LogApprovalStatus.REJECTED.value:
        return "Changes requested"
    return "Under review"


def matches_view_mode(
    scheduled_date: date | None,
    *,
    view_mode: str,
    month: str | None,
    day: str | None,
) -> bool:
    iso = _session_date_iso(scheduled_date)
    if view_mode == "all":
        return True
    if not iso:
        return False
    if view_mode == "month":
        return bool(month) and iso.startswith(month)
    if view_mode == "day":
        return bool(day) and iso == day
    return True


def matches_year(scheduled_date: date | None, year: str | None) -> bool:
    if not year:
        return True
    iso = _session_date_iso(scheduled_date)
    return bool(iso) and iso.startswith(f"{year}-")


def matches_staff_status_filter(
    session: TherapySession | None,
    log: DailyLog | None,
    status_filter: str | None,
) -> bool:
    if not status_filter:
        return True

    session_status = str(session.status.value if session and hasattr(session.status, "value") else session.status or "").upper()
    approval = _approval_value(log)
    has_log = log is not None
    is_ongoing = session_status in ONGOING_SESSION_STATUSES and not has_log
    has_time_edit = _session_has_time_edit(session, log)

    if status_filter == "approved":
        return approval == LogApprovalStatus.APPROVED.value
    if status_filter == "pending_review":
        return approval == LogApprovalStatus.PENDING.value
    if status_filter == "rejected":
        return approval == LogApprovalStatus.REJECTED.value
    if status_filter == "ongoing":
        return is_ongoing
    if status_filter == "no_log":
        return not has_log and session_status not in ONGOING_SESSION_STATUSES
    if status_filter == "cancelled":
        return session_status == SessionStatus.CANCELLED.value
    if status_filter == "child_on_leave":
        return _is_child_on_leave(session, log)
    if status_filter == "therapist_on_leave":
        return _is_therapist_on_leave(session, log)
    if status_filter == "resubmitted":
        return bool(log and log.resubmitted_at)
    if status_filter == "times_edited":
        return has_time_edit
    return True


def matches_parent_attendance_filter(log: DailyLog, attendance_filter: str | None) -> bool:
    if not attendance_filter:
        return True
    att = (log.attendance_status or "").upper()
    if attendance_filter == "COMPLETED":
        return att not in {"CLIENT_ABSENT", "CLIENT_LEAVE", "THERAPIST_LEAVE"}
    if attendance_filter == "CHILD_LEAVE":
        return att in {"CLIENT_ABSENT", "CLIENT_LEAVE"}
    if attendance_filter == "THERAPIST_LEAVE":
        return att == "THERAPIST_LEAVE"
    return True


def _is_under_review_therapist_leave_log(log: DailyLog) -> bool:
    att = (log.attendance_status or "").upper()
    return att == "THERAPIST_LEAVE" and _approval_value(log) != LogApprovalStatus.APPROVED.value


def _filter_summary_label(
    *,
    view_mode: str,
    month: str | None,
    day: str | None,
    year: str | None,
    status_filter: str | None,
    attendance_filter: str | None,
) -> str:
    parts: list[str] = []
    if view_mode == "day" and day:
        parts.append(f"Date: {day}")
    elif view_mode == "month" and month:
        parts.append(f"Month: {month}")
    elif year:
        parts.append(f"Year: {year}")
    else:
        parts.append("Period: all dates")
    if status_filter:
        parts.append(f"Status filter: {status_filter.replace('_', ' ')}")
    if attendance_filter:
        parts.append(f"Attendance filter: {attendance_filter.replace('_', ' ').lower()}")
    return " · ".join(parts)


def _safe_filename_part(value: str | None, fallback: str) -> str:
    raw = re.sub(r"[^\w.\-]+", "_", str(value or "").strip())[:40].strip("._")
    return raw or fallback


def export_filename(*, case_code: str | None, period_label: str) -> str:
    case_part = _safe_filename_part(case_code, "case")
    period_part = _safe_filename_part(period_label, "export")
    return f"session_logs_{case_part}_{period_part}.xlsx"


def _therapist_names(db: Session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.full_name, User.email).where(User.id.in_(user_ids))).all()
    out: dict[int, str] = {}
    for user_id, full_name, email in rows:
        out[user_id] = (full_name or email or f"Therapist #{user_id}").strip()
    return out


def _load_case_context(db: Session, case_id: int) -> tuple[Case, list[TherapySession], list[DailyLog], dict[int, str]]:
    case = db.scalar(
        select(Case)
        .where(Case.id == case_id)
        .options(selectinload(Case.child))
    )
    if not case:
        raise ValueError("Case not found")

    sessions = list(
        db.scalars(
            select(TherapySession)
            .where(TherapySession.case_id == case_id)
            .order_by(TherapySession.scheduled_date.desc(), TherapySession.id.desc())
        ).all()
    )
    logs = list(
        db.scalars(
            select(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(TherapySession.case_id == case_id)
            .options(selectinload(DailyLog.session))
        ).all()
    )
    therapist_ids = {s.therapist_user_id for s in sessions if s.therapist_user_id}
    therapist_ids.update(
        log.session.therapist_user_id
        for log in logs
        if log.session and log.session.therapist_user_id
    )
    return case, sessions, logs, _therapist_names(db, therapist_ids)


def collect_staff_export_rows(
    db: Session,
    *,
    case_id: int,
    view_mode: str = "all",
    month: str | None = None,
    day: str | None = None,
    year: str | None = None,
    status_filter: str | None = None,
) -> tuple[Case, list[ExportRow]]:
    case, sessions, logs, therapist_names = _load_case_context(db, case_id)
    logs_by_session_id = {log.session_id: log for log in logs if log.session_id is not None}
    session_ids = {s.id for s in sessions}
    orphan_logs = [log for log in logs if log.session_id not in session_ids]

    rows: list[ExportRow] = []

    for session in sessions:
        log = logs_by_session_id.get(session.id)
        scheduled = session.scheduled_date
        if not matches_view_mode(scheduled, view_mode=view_mode, month=month, day=day):
            continue
        if not matches_year(scheduled, year):
            continue
        if not matches_staff_status_filter(session, log, status_filter):
            continue
        therapist_name = therapist_names.get(session.therapist_user_id, "")
        rows.append(
            ExportRow(
                scheduled_date=scheduled,
                time_label=_session_time_label(session, log),
                therapist_name=therapist_name,
                status_label=_staff_status_label(session, log),
                log=log,
            )
        )

    for log in orphan_logs:
        session = log.session
        scheduled = session.scheduled_date if session else None
        if not matches_view_mode(scheduled, view_mode=view_mode, month=month, day=day):
            continue
        if not matches_year(scheduled, year):
            continue
        if not matches_staff_status_filter(None, log, status_filter):
            continue
        therapist_id = session.therapist_user_id if session else None
        therapist_name = therapist_names.get(therapist_id, "") if therapist_id else ""
        rows.append(
            ExportRow(
                scheduled_date=scheduled,
                time_label=_session_time_label(session, log),
                therapist_name=therapist_name,
                status_label=_staff_status_label(session, log),
                log=log,
            )
        )

    rows.sort(key=lambda row: (_session_date_iso(row.scheduled_date), row.time_label), reverse=True)
    return case, rows


def collect_parent_export_rows(
    db: Session,
    *,
    case_id: int,
    view_mode: str = "all",
    month: str | None = None,
    day: str | None = None,
    attendance_filter: str | None = None,
) -> tuple[Case, list[ExportRow]]:
    case, _sessions, logs, therapist_names = _load_case_context(db, case_id)
    rows: list[ExportRow] = []

    for log in logs:
        if not log.submitted_at:
            continue
        if _is_under_review_therapist_leave_log(log):
            continue
        session = log.session
        if not session:
            continue
        scheduled = session.scheduled_date
        if not matches_view_mode(scheduled, view_mode=view_mode, month=month, day=day):
            continue
        if not matches_parent_attendance_filter(log, attendance_filter):
            continue
        therapist_name = therapist_names.get(session.therapist_user_id, "")
        rows.append(
            ExportRow(
                scheduled_date=scheduled,
                time_label=_session_time_label(session, log),
                therapist_name=therapist_name,
                status_label=_parent_status_label(log),
                log=log,
            )
        )

    rows.sort(key=lambda row: (_session_date_iso(row.scheduled_date), row.time_label), reverse=True)
    return case, rows


def build_case_session_logs_xlsx(
    *,
    db: Session,
    case: Case,
    rows: list[ExportRow],
    user: User,
    audience: Audience,
    include_content: bool,
    filter_summary: str,
) -> bytes:
    import openpyxl

    meta = export_meta(user)
    child_name = case.child.full_name if getattr(case, "child", None) else ""
    parent_info = parent_by_child(db, {case.child_id}).get(case.child_id) if case.child_id else None
    parent_name = case_people_export_fields(
        case, parent_info=parent_info, include_therapist=False
    )["Parent Name"]
    case_code = case.case_code or f"case_{case.id}"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Session logs"

    subtitle = f"{case_code} · {child_name}".strip(" · ")
    preamble_meta = {
        **meta,
        "case_id": str(case.id),
        "case_code": case_code,
        "child_name": child_name or "—",
        "parent_name": parent_name or "—",
        "filters": filter_summary,
        "include_content": "Yes" if include_content else "No",
    }
    for row in xlsx_preamble_rows("Session logs export", subtitle, meta):
        ws.append(row)
    ws.append([f"Case ID: {case.id}"])
    ws.append([f"Case code: {case_code}"])
    ws.append([f"Child: {child_name or '—'}"])
    ws.append([f"Parent: {parent_name or '—'}"])
    ws.append([f"Filters: {filter_summary}"])
    ws.append([f"Include log content: {'Yes' if include_content else 'No'}"])
    ws.append([])

    status_header = "Status" if audience == "parent" else "Approval status"
    headers = ["Date", "Time", "Therapist", status_header]
    content_columns = _PARENT_CONTENT_COLUMNS if audience == "parent" else _STAFF_CONTENT_COLUMNS
    if include_content:
        headers.extend(label for _, label in content_columns)
    ws.append(headers)

    for row in rows:
        values = [
            _session_date_iso(row.scheduled_date),
            row.time_label,
            row.therapist_name,
            row.status_label,
        ]
        if include_content:
            log = row.log
            for field, _label in content_columns:
                values.append(getattr(log, field, "") or "" if log else "")
        ws.append(values)

    for row in xlsx_footer_rows(meta):
        ws.append(row)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def export_staff_case_session_logs_xlsx(
    db: Session,
    *,
    case_id: int,
    user: User,
    view_mode: str = "all",
    month: str | None = None,
    day: str | None = None,
    year: str | None = None,
    status_filter: str | None = None,
    include_content: bool = False,
) -> tuple[bytes, str]:
    case, rows = collect_staff_export_rows(
        db,
        case_id=case_id,
        view_mode=view_mode,
        month=month,
        day=day,
        year=year,
        status_filter=status_filter or None,
    )
    filter_summary = _filter_summary_label(
        view_mode=view_mode,
        month=month,
        day=day,
        year=year,
        status_filter=status_filter,
        attendance_filter=None,
    )
    content = build_case_session_logs_xlsx(
        db=db,
        case=case,
        rows=rows,
        user=user,
        audience="staff",
        include_content=include_content,
        filter_summary=filter_summary,
    )
    period = day or month or year or "all"
    filename = export_filename(case_code=case.case_code, period_label=period)
    return content, filename


def export_parent_case_session_logs_xlsx(
    db: Session,
    *,
    case_id: int,
    user: User,
    view_mode: str = "all",
    month: str | None = None,
    day: str | None = None,
    attendance_filter: str | None = None,
    include_content: bool = False,
) -> tuple[bytes, str]:
    case, rows = collect_parent_export_rows(
        db,
        case_id=case_id,
        view_mode=view_mode,
        month=month,
        day=day,
        attendance_filter=attendance_filter or None,
    )
    filter_summary = _filter_summary_label(
        view_mode=view_mode,
        month=month,
        day=day,
        year=None,
        status_filter=None,
        attendance_filter=attendance_filter,
    )
    content = build_case_session_logs_xlsx(
        db=db,
        case=case,
        rows=rows,
        user=user,
        audience="parent",
        include_content=include_content,
        filter_summary=filter_summary,
    )
    period = day or month or "all"
    filename = export_filename(case_code=case.case_code, period_label=period)
    return content, filename
