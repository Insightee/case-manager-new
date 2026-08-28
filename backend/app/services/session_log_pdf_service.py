"""PDF export for a single approved session log."""

from __future__ import annotations

import io
import re
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.session_times import effective_session_datetimes
from app.core.timezone import IST, ensure_utc_aware
from app.models.case import Case
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.services.parent_home_service import _attendance_label
from app.services.reports_export_helpers import parent_by_child, case_people_export_fields

NOT_APPROVED_DOWNLOAD_MESSAGE = (
    "This log is still under review. Download is available after it's approved."
)

_STAFF_SECTIONS = (
    ("activities_done", "What you did today"),
    ("goals_addressed", "Goals worked on"),
    ("parent_notes", "Update for family"),
    ("session_notes", "Session notes (internal)"),
    ("observations", "Clinical observations"),
    ("follow_ups", "Follow-ups"),
    ("late_reason", "Late reason"),
)

_PARENT_SECTIONS = (
    ("parent_notes", "Update for family"),
    ("activities_done", "What we did today"),
    ("goals_addressed", "Goals worked on"),
    ("follow_ups", "What's next"),
)


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _safe_filename_part(value: str | None, fallback: str) -> str:
    raw = re.sub(r"[^\w.\-]+", "_", (value or "").strip())[:40].strip("._")
    return raw or fallback


def session_log_pdf_filename(*, case_code: str | None, scheduled: date | None, log_id: int) -> str:
    date_part = scheduled.isoformat() if scheduled else "session"
    case_part = _safe_filename_part(case_code, f"log_{log_id}")
    return f"session_log_{case_part}_{date_part}.pdf"


def _fmt_ist_range(start: datetime | None, end: datetime | None) -> str | None:
    if not start or not end:
        return None
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


def _session_when(session: TherapySession | None, log: DailyLog) -> str:
    parts: list[str] = []
    scheduled = session.scheduled_date if session else None
    if scheduled:
        parts.append(scheduled.strftime("%a, %d %b %Y"))
    if session:
        start, end = effective_session_datetimes(session, log)
        clock = _fmt_ist_range(start, end)
        if clock:
            parts.append(clock)
        elif session.start_time and session.end_time:
            parts.append(f"{_fmt_clock(session.start_time)} – {_fmt_clock(session.end_time)}")
    return " · ".join(parts) if parts else "Session date not recorded"


def _child_name(case: Case | None) -> str:
    if case and getattr(case, "child", None):
        return case.child.full_name or "Child"
    return "Child"


def _paragraphs_from_text(text: str) -> list[str]:
    chunks = [line.strip() for line in (text or "").splitlines()]
    return [chunk for chunk in chunks if chunk] or [text.strip()]


def _parent_name(db: Session | None, case: Case | None, parent_name: Optional[str] = None) -> str:
    if parent_name:
        return parent_name.strip()
    if not db or not case or not case.child_id:
        return ""
    info = parent_by_child(db, {case.child_id}).get(case.child_id)
    return case_people_export_fields(case, parent_info=info, include_therapist=False)["Parent Name"]


def build_session_log_pdf(
    *,
    log: DailyLog,
    session: Optional[TherapySession],
    case: Optional[Case],
    therapist_name: Optional[str],
    audience: str,
    generated_by: Optional[str] = None,
    generated_at: Optional[str] = None,
    db: Session | None = None,
    parent_name: Optional[str] = None,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    parent_facing = audience == "parent"
    title = "Session note" if parent_facing else "Session log"
    child = _child_name(case)
    parent = _parent_name(db, case, parent_name)
    case_code = case.case_code if case else "—"
    when = _session_when(session, log)
    attendance = _attendance_label(log.attendance_status) if parent_facing else (log.attendance_status or "—")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=48, bottomMargin=48)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SessionLogTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=8,
        textColor=colors.HexColor("#1e293b"),
    )
    meta_style = ParagraphStyle(
        "SessionLogMeta",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=4,
    )
    heading_style = ParagraphStyle(
        "SessionLogHeading",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceBefore=12,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "SessionLogBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
        spaceAfter=6,
        textColor=colors.HexColor("#0f172a"),
    )
    empty_style = ParagraphStyle(
        "SessionLogEmpty",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#64748b"),
        spaceBefore=16,
    )

    identity = f"{child} · {case_code}"
    if parent:
        identity = f"{child} · {parent} · {case_code}"
    story = [
        Paragraph(_escape(title), title_style),
        Paragraph(_escape(identity), meta_style),
        Paragraph(_escape(when), meta_style),
    ]
    if therapist_name:
        story.append(Paragraph(_escape(f"Therapist: {therapist_name}"), meta_style))
    story.append(Paragraph(_escape(f"Attendance: {attendance}"), meta_style))
    story.append(Paragraph("Status: Approved", meta_style))
    story.append(Spacer(1, 8))

    sections = _PARENT_SECTIONS if parent_facing else _STAFF_SECTIONS
    wrote_section = False
    for key, label in sections:
        value = getattr(log, key, None)
        if not value or not str(value).strip():
            continue
        wrote_section = True
        story.append(Paragraph(f"<b>{_escape(label)}</b>", heading_style))
        for line in _paragraphs_from_text(str(value)):
            story.append(Paragraph(_escape(line), body_style))

    if not wrote_section:
        story.append(
            Paragraph(
                "This session note has no additional written details."
                if parent_facing
                else "This log has no additional written details.",
                empty_style,
            )
        )

    if generated_by or generated_at:
        story.append(Spacer(1, 20))
        parts = []
        if generated_by:
            parts.append(f"Downloaded by {_escape(generated_by)}")
        if generated_at:
            parts.append(_escape(generated_at))
        story.append(Paragraph(" · ".join(parts), meta_style))

    doc.build(story)
    return buf.getvalue()
