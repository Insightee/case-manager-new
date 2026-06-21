"""Day-wise session log PDF export for a single case."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from typing import Optional
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import case_scope_check, user_has_permission
from app.models.session import Session as TherapySession, SessionStatus
from app.services.export_document_service import export_meta
from app.services.report_log_query import parse_report_month
from app.services import case_service

LOG_FIELDS = [
    ("attendance_status", "Attendance"),
    ("activities_done", "What you did today"),
    ("goals_addressed", "Goals worked on"),
    ("parent_notes", "Update for family"),
    ("session_notes", "Session notes (internal)"),
    ("observations", "Clinical observations"),
    ("follow_ups", "Follow-ups"),
    ("late_reason", "Late reason"),
]


def _esc(text: str | None) -> str:
    if not text:
        return "—"
    return escape(str(text).strip()).replace("\n", "<br/>")


def _session_time_label(session) -> str:
    if session.actual_start_at and session.actual_end_at:
        start = session.actual_start_at.strftime("%H:%M")
        end = session.actual_end_at.strftime("%H:%M")
        return f"{start}–{end}"
    if session.start_time and session.end_time:
        return f"{str(session.start_time)[:5]}–{str(session.end_time)[:5]}"
    return "—"


def _weekday_label(d: date) -> str:
    return d.strftime("%A")


def _month_label(year: int | None, month_num: int | None) -> str:
    if year and month_num:
        return date(year, month_num, 1).strftime("%B %Y")
    return "All sessions"


def _parse_month(month: Optional[str]) -> tuple[int | None, int | None]:
    if not month:
        return None, None
    parsed = parse_report_month(month)
    if parsed:
        return parsed
    if "-" in month:
        parts = month.split("-", 1)
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            pass
    return None, None


def list_case_sessions_for_log_pdf(
    db: Session,
    user,
    *,
    case_id: int,
    month: Optional[str] = None,
) -> tuple:
    """Sessions in the calendar month for PDF export (matches case profile logs tab scope)."""
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise ValueError("Case not found")

    if user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        from app.models.assignment import CaseAssignment, CaseAssignmentStatus

        active = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.therapist_user_id == user.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        if not active:
            raise ValueError("Case not found")

    year, month_num = _parse_month(month)

    stmt = (
        select(TherapySession)
        .where(TherapySession.case_id == case_id)
        .options(selectinload(TherapySession.daily_log))
        .order_by(TherapySession.scheduled_date.asc(), TherapySession.start_time.asc())
    )

    if year is not None and month_num is not None:
        start = date(year, month_num, 1)
        end = date(year, month_num, monthrange(year, month_num)[1])
        stmt = stmt.where(
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )

    if user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        stmt = stmt.where(TherapySession.therapist_user_id == user.id)

    sessions = list(db.scalars(stmt).all())
    return case, sessions, year, month_num


def build_case_session_logs_pdf(
    db: Session,
    user,
    *,
    case_id: int,
    month: Optional[str] = None,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    case, sessions, year, month_num = list_case_sessions_for_log_pdf(
        db, user, case_id=case_id, month=month
    )
    child_name = case.child.full_name if case.child else "Client"
    case_code = case.case_code or f"Case #{case_id}"

    meta = export_meta(user)
    styles = getSampleStyleSheet()
    brand = colors.HexColor("#416656")
    brand_soft = colors.HexColor("#c3ecd7")
    muted = colors.HexColor("#64748b")
    border = colors.HexColor("#e2e8f0")
    warn = colors.HexColor("#b91c1c")

    title_style = ParagraphStyle(
        "LogExportTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=colors.white,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "LogExportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#d3e7dd"),
        spaceAfter=0,
    )
    day_style = ParagraphStyle(
        "LogDayHeading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=brand,
        spaceBefore=6,
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "LogMeta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=muted,
    )
    label_style = ParagraphStyle(
        "LogFieldLabel",
        parent=styles["Normal"],
        fontSize=9,
        textColor=muted,
        leading=12,
    )
    value_style = ParagraphStyle(
        "LogFieldValue",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )
    session_style = ParagraphStyle(
        "LogSessionLabel",
        parent=styles["Normal"],
        fontSize=10,
        textColor=brand,
        fontName="Helvetica-Bold",
    )
    missing_style = ParagraphStyle(
        "LogMissing",
        parent=styles["Normal"],
        fontSize=10,
        textColor=warn,
        fontName="Helvetica-Bold",
    )

    buf = __import__("io").BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Session logs — {case_code}",
    )

    elements = []

    header_table = Table(
        [[Paragraph("Session Logs", title_style)], [Paragraph(f"{child_name} · {case_code}", subtitle_style)]],
        colWidths=[doc.width],
    )
    header_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), brand),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, 0), 14),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
        ])
    )
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(_month_label(year, month_num), meta_style))

    log_count = sum(1 for s in sessions if s.daily_log)
    missing_count = sum(
        1 for s in sessions if s.status == SessionStatus.COMPLETED and not s.daily_log
    )
    elements.append(
        Paragraph(
            f"{len(sessions)} session(s) · {log_count} log(s) submitted · {missing_count} missing",
            meta_style,
        )
    )
    elements.append(Paragraph(f"Generated by {meta['generated_by']} · {meta['generated_at']}", meta_style))
    elements.append(Spacer(1, 14))

    by_day: dict[date, list] = defaultdict(list)
    for session in sessions:
        if session.scheduled_date:
            by_day[session.scheduled_date].append(session)

    if not by_day:
        elements.append(
            Paragraph(
                "No sessions recorded for this period.",
                value_style,
            )
        )
    else:
        for day in sorted(by_day.keys()):
            day_sessions = by_day[day]
            day_header = Table(
                [[Paragraph(f"{day.strftime('%d-%m-%Y')} · {_weekday_label(day)}", day_style)]],
                colWidths=[doc.width],
            )
            day_header.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), brand_soft),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ])
            )
            elements.append(day_header)
            elements.append(Spacer(1, 6))

            for session in day_sessions:
                log = session.daily_log
                if log:
                    status = log.approval_status.value if hasattr(log.approval_status, "value") else str(log.approval_status)
                    elements.append(
                        Paragraph(
                            f"Session · {_session_time_label(session)} · {status.replace('_', ' ').title()}",
                            session_style,
                        )
                    )
                    elements.append(Spacer(1, 4))

                    rows = []
                    for key, label in LOG_FIELDS:
                        val = getattr(log, key, None)
                        if not val:
                            continue
                        rows.append([
                            Paragraph(label, label_style),
                            Paragraph(_esc(val), value_style),
                        ])
                    if rows:
                        field_table = Table(rows, colWidths=[doc.width * 0.32, doc.width * 0.68])
                        field_table.setStyle(
                            TableStyle([
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                ("TOPPADDING", (0, 0), (-1, -1), 6),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                ("GRID", (0, 0), (-1, -1), 0.5, border),
                                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                            ])
                        )
                        elements.append(field_table)
                    else:
                        elements.append(Paragraph("Log submitted — no narrative fields recorded.", value_style))
                elif session.status == SessionStatus.COMPLETED:
                    elements.append(
                        Paragraph(
                            f"Missing log · {_session_time_label(session)} · session completed, log not submitted",
                            missing_style,
                        )
                    )
                else:
                    status = session.status.value if hasattr(session.status, "value") else str(session.status)
                    elements.append(
                        Paragraph(
                            f"Session · {_session_time_label(session)} · {status.replace('_', ' ').title()} · no log yet",
                            meta_style,
                        )
                    )
                elements.append(Spacer(1, 10))

            elements.append(Spacer(1, 6))

    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(
            f"InsighteCase session log export · {case_code} · {meta['generated_at']}",
            meta_style,
        )
    )

    doc.build(elements)
    buf.seek(0)
    return buf.read()
