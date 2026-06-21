"""Compile structured monthly report sections from session evidence."""

from __future__ import annotations

import html

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import MonthlyReportSection, SessionGoalEntry, StrategyUseEvent
from app.models.report import MonthlyReport, ReportStatus
from app.services import report_compile_service
from app.services.report_log_query import submitted_logs_for_report_month

SECTION_KEYS = (
    "month_summary",
    "sessions",
    "goal_progress",
    "strategies",
    "barriers",
    "parent_summary",
    "next_month",
    "internal_cm_notes",
    "evidence_annexure",
)


def _esc(text: str | None) -> str:
    return html.escape((text or "").strip())


def compile_evidence_v2(db: Session, user, report: MonthlyReport) -> dict:
    if report.status not in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Report is locked; only draft/rejected can compile")

    logs = submitted_logs_for_report_month(db, report)
    session_html = report_compile_service.compile_body_html_from_logs(logs)
    goal_lines = []
    for log in logs:
        entries = db.scalars(
            select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id)
        ).all()
        for e in entries:
            goal_lines.append(f"<li>{_esc(e.goal_label)} — {_esc(e.response_note or 'Noted in session')}</li>")
    goal_html = f"<ul>{''.join(goal_lines)}</ul>" if goal_lines else "<p><em>No structured goal entries.</em></p>"

    strat_lines = []
    for log in logs:
        for s in db.scalars(
            select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == log.id)
        ).all():
            strat_lines.append(f"<li>{_esc(s.strategy_label)} — {_esc(s.outcome_note or '')}</li>")
    strat_html = f"<ul>{''.join(strat_lines)}</ul>" if strat_lines else "<p><em>No strategy use recorded.</em></p>"

    sections_data = {
        "month_summary": f"<p>Compiled summary for {report.month}.</p>",
        "sessions": session_html,
        "goal_progress": goal_html,
        "strategies": strat_html,
        "barriers": "<p><em>Add barriers as needed.</em></p>",
        "parent_summary": "<p><em>Draft parent-facing summary — review before publish.</em></p>",
        "next_month": f"<p>{_esc(report_compile_service.collect_follow_ups(logs)) or '—'}</p>",
        "internal_cm_notes": "<p><em>Internal CM notes only.</em></p>",
        "evidence_annexure": goal_html,
    }

    existing = {
        s.section_key: s
        for s in db.scalars(
            select(MonthlyReportSection).where(MonthlyReportSection.report_id == report.id)
        ).all()
    }
    for idx, key in enumerate(SECTION_KEYS):
        vis = "INTERNAL_ONLY" if key in ("internal_cm_notes", "evidence_annexure") else "CLIENT_VISIBLE_AFTER_APPROVAL"
        if key in existing:
            row = existing[key]
            row.content_html = sections_data[key]
            row.sort_order = idx
            row.visibility = vis
        else:
            db.add(
                MonthlyReportSection(
                    report_id=report.id,
                    section_key=key,
                    content_html=sections_data[key],
                    visibility=vis,
                    sort_order=idx,
                )
            )

    combined = []
    for key in SECTION_KEYS:
        combined.append(f"<h2>{key.replace('_', ' ').title()}</h2>{sections_data[key]}")
    report.body_html = "\n".join(combined)
    from app.services.report_image_service import sync_summary_from_body

    sync_summary_from_body(report)
    db.flush()
    return {"report_id": report.id, "sections": list(SECTION_KEYS), "body_html_updated": True}
