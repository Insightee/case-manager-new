"""Compile monthly report body_html from submitted session logs."""
from __future__ import annotations

import html
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import case_scope_check
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.report import MonthlyReport, ReportStatus
from app.services import case_service
from app.services.report_image_service import sync_summary_from_body
from app.services.report_log_query import submitted_logs_for_report_month

CompileMode = Literal["replace", "append"]


def _escape(text: str | None) -> str:
    return html.escape((text or "").strip())


def _section(label: str, value: str | None) -> str:
    if not (value or "").strip():
        return ""
    return f"<p><strong>{_escape(label)}:</strong> {_escape(value)}</p>"


def _log_block_html(log: DailyLog) -> str:
    s = log.session
    if not s:
        return ""
    date_label = s.scheduled_date.isoformat() if s.scheduled_date else "Visit"
    pending = log.approval_status == LogApprovalStatus.PENDING
    badge = (
        ' <em style="color:#b45309">(Pending admin review)</em>'
        if pending
        else ""
    )
    parts = [f"<h2>Visit — {_escape(date_label)}{badge}</h2>"]
    if log.attendance_status:
        parts.append(_section("Attendance", log.attendance_status))
    parts.append(_section("What we did", log.activities_done))
    parts.append(_section("Goals worked on", log.goals_addressed))
    parts.append(_section("Update for family", log.parent_notes))
    parts.append(_section("Clinical observations", log.observations))
    parts.append(_section("Follow-ups", log.follow_ups))
    parts.append(_section("Session notes (internal)", log.session_notes))
    return "\n".join(p for p in parts if p)


def compile_body_html_from_logs(logs: list[DailyLog]) -> str:
    blocks = [_log_block_html(log) for log in logs]
    blocks = [b for b in blocks if b]
    if not blocks:
        return "<p><em>No submitted session logs for this month.</em></p>"
    return "\n".join(blocks)


def collect_follow_ups(logs: list[DailyLog]) -> str:
    lines = []
    for log in logs:
        if not (log.follow_ups or "").strip():
            continue
        s = log.session
        d = s.scheduled_date.isoformat() if s and s.scheduled_date else "Visit"
        lines.append(f"{d}: {log.follow_ups.strip()}")
    return "\n".join(lines)


def generate_monthly_report_from_logs(
    db: Session,
    user,
    report: MonthlyReport,
    *,
    mode: CompileMode = "replace",
) -> MonthlyReport:
    case = case_service.get_case(db, report.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Report not found")
    if report.therapist_user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status not in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Only draft or rejected reports can be edited")

    logs = submitted_logs_for_report_month(db, report)
    compiled = compile_body_html_from_logs(logs)

    if mode == "append" and (report.body_html or "").strip():
        report.body_html = f"{report.body_html.rstrip()}\n<hr/>\n{compiled}"
    else:
        report.body_html = compiled

    if not (report.plan_next_month or "").strip():
        follow = collect_follow_ups(logs)
        if follow:
            report.plan_next_month = follow

    sync_summary_from_body(report)
    if report.status == ReportStatus.REJECTED:
        report.status = ReportStatus.DRAFT
        report.reviewer_comment = None
    return report
