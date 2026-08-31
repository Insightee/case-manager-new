"""Admin Excel export for session-log duration audit outliers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Optional

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import case_scope_check
from app.core.session_times import effective_session_datetimes
from app.core.timezone import IST, ensure_utc_aware
from app.models.case import Case
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.models.user import User
from app.services.export_document_service import export_meta, xlsx_footer_rows, xlsx_preamble_rows
from app.services import session_duration_compliance_service as duration_svc


def _parse_month(month: str | None) -> tuple[date | None, date | None]:
    if not month:
        return None, None
    raw = month.strip()
    if len(raw) == 7 and raw[4] == "-":
        year = int(raw[:4])
        mo = int(raw[5:7])
        start = date(year, mo, 1)
        if mo == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, mo + 1, 1) - timedelta(days=1)
        return start, end
    return None, None


def _fmt_ist(dt: datetime | None) -> str:
    if dt is None:
        return ""
    aware = ensure_utc_aware(dt)
    if aware is None:
        return ""
    return aware.astimezone(IST).strftime("%Y-%m-%d %H:%M IST")


def _scheduled_window(session: TherapySession) -> str:
    if not session.scheduled_date:
        return ""
    start = session.start_time.isoformat()[:5] if session.start_time else ""
    end = session.end_time.isoformat()[:5] if session.end_time else ""
    if start and end:
        return f"{session.scheduled_date.isoformat()} {start}–{end}"
    return session.scheduled_date.isoformat()


def build_duration_outliers_xlsx(
    db: Session,
    *,
    user: User,
    date_from: date,
    date_to: date,
    product_module: str | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> tuple[bytes, str]:
    stmt = (
        select(DailyLog)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .join(Case, TherapySession.case_id == Case.id)
        .options(
            selectinload(DailyLog.session).selectinload(TherapySession.case),
        )
        .where(
            TherapySession.scheduled_date >= date_from,
            TherapySession.scheduled_date <= date_to,
        )
        .order_by(TherapySession.scheduled_date.desc(), DailyLog.id.desc())
    )
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id:
        stmt = stmt.where(TherapySession.case_id == case_id)

    logs = db.scalars(stmt).all()
    rows: list[list] = []
    for log in logs:
        session = log.session
        if not session or not session.case:
            continue
        case = session.case
        if not case_scope_check(db, user, case):
            continue
        if not duration_svc.is_billable_session_log(session, log):
            continue
        duration_mins = duration_svc.effective_duration_minutes(session, log)
        flag = duration_svc.audit_outlier_flag(case.product_module, duration_mins)
        if not flag:
            continue
        therapist = db.get(User, session.therapist_user_id)
        eff_start, eff_end = effective_session_datetimes(session, log)
        day_type = case.day_type.value if case.day_type else ""
        approval = log.approval_status.value if hasattr(log.approval_status, "value") else str(log.approval_status)
        rows.append(
            [
                log.id,
                session.id,
                session.scheduled_date.isoformat(),
                case.case_code,
                case.product_module,
                day_type,
                therapist.full_name if therapist else "",
                therapist.email if therapist else "",
                duration_mins,
                flag,
                duration_svc.audit_outlier_label(flag),
                _scheduled_window(session),
                _fmt_ist(eff_start),
                _fmt_ist(eff_end),
                approval,
                bool(session.auto_ended),
                bool(getattr(session, "actual_times_edited", False)),
            ]
        )

    meta = export_meta(user)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Duration outliers"
    for row in xlsx_preamble_rows(
        "Session log duration outliers",
        f"Period: {date_from.isoformat()} to {date_to.isoformat()}",
        meta,
    ):
        ws.append(row)
    headers = [
        "Log ID",
        "Session ID",
        "Scheduled date",
        "Case code",
        "Product module",
        "Day type",
        "Therapist",
        "Therapist email",
        "Duration (min)",
        "Flag code",
        "Flag reason",
        "Scheduled window",
        "Effective start (IST)",
        "Effective end (IST)",
        "Approval status",
        "Auto ended",
        "Times edited",
    ]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    for row in xlsx_footer_rows(meta):
        ws.append(row)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"session_duration_outliers_{date_from}_{date_to}.xlsx"
    return buf.read(), filename


def resolve_export_date_range(
    *,
    date_from: str | None,
    date_to: str | None,
    month: str | None,
) -> tuple[date, date]:
    month_start, month_end = _parse_month(month)
    if month_start and month_end:
        return month_start, month_end
    today = date.today()
    d_from = date.fromisoformat(date_from) if date_from else today.replace(day=1)
    d_to = date.fromisoformat(date_to) if date_to else today
    return d_from, d_to
