"""Strip internal fields for CM/therapist parent-preview only."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import MonthlyReportSection
from app.models.report import MonthlyReport

INTERNAL_SECTION_KEYS = frozenset({"internal_cm_notes", "evidence_annexure"})


def serialize_parent_safe_monthly(
    db: Session,
    report: MonthlyReport,
    *,
    case_code: str = "",
    child_name: str = "",
) -> dict:
    out = serialize_monthly_parent_preview(db, report)
    out["case_code"] = case_code
    out["child_name"] = child_name
    return out


def serialize_monthly_parent_preview(db: Session, report: MonthlyReport) -> dict:
    sections = db.scalars(
        select(MonthlyReportSection)
        .where(MonthlyReportSection.report_id == report.id)
        .order_by(MonthlyReportSection.sort_order)
    ).all()
    safe_sections = []
    for s in sections:
        if s.section_key in INTERNAL_SECTION_KEYS:
            continue
        if s.visibility == "INTERNAL_ONLY":
            continue
        safe_sections.append(
            {
                "section_key": s.section_key,
                "content_html": _strip_internal_notes(s.content_html or ""),
            }
        )
    body = report.body_html or ""
    if not safe_sections and body:
        safe_sections.append({"section_key": "body", "content_html": _strip_internal_notes(body)})
    return {
        "report_id": report.id,
        "month": report.month,
        "status": report.status.value if hasattr(report.status, "value") else report.status,
        "sections": safe_sections,
        "preview_note": "Parent-safe preview — not published to parent portal.",
    }


def _strip_internal_notes(html: str) -> str:
    text = re.sub(r"(?i)session notes \(internal\).*?(</p>|$)", "", html)
    text = re.sub(r"(?i)internal cm notes.*?(</p>|$)", "", text)
    return text.strip()
