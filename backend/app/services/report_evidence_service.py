from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.clinical_report import ClinicalReport, ClinicalReportEvidence, ClinicalReportSection
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.report_engine_constants import REQUIRED_OBSERVATION_SECTION_KEYS


def attach_case_document(
    db: Session,
    report: ClinicalReport,
    *,
    case_document_id: int,
    section_key: str | None = None,
    evidence_label: str | None = None,
) -> ClinicalReportEvidence:
    from app.models.case_document import CaseDocument

    doc = db.get(CaseDocument, case_document_id)
    if not doc or doc.case_id != report.case_id:
        raise ValueError("Document not found for this case")
    existing = db.scalar(
        select(ClinicalReportEvidence).where(
            ClinicalReportEvidence.report_id == report.id,
            ClinicalReportEvidence.source_type == "uploaded_document",
            ClinicalReportEvidence.source_id == doc.id,
        )
    )
    if existing:
        return existing
    row = ClinicalReportEvidence(
        report_id=report.id,
        case_id=report.case_id,
        source_type="uploaded_document",
        source_id=doc.id,
        section_key=section_key,
        evidence_label=evidence_label or doc.title,
    )
    db.add(row)
    db.flush()
    return row

    for field in (log.observations, log.session_notes, log.activities_done, log.goals_addressed):
        if field and str(field).strip():
            return True
    return False


def _log_snippet(log: DailyLog, limit: int = 120) -> str:
    for field in (log.observations, log.session_notes, log.activities_done, log.goals_addressed):
        text = (field or "").strip()
        if text:
            return text if len(text) <= limit else f"{text[:limit].rstrip()}…"
    return ""


def evidence_summary(db: Session, report: ClinicalReport) -> dict:
    sections = list(
        db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all()
    )
    completed = sum(1 for s in sections if s.completion_status == "completed")
    internal_notes = sum(1 for s in sections if (s.internal_notes or "").strip())
    parent_inputs = 1 if any(s.section_key == "parent_inputs" and (s.narrative_text or "").strip() for s in sections) else 0
    school_inputs = 1 if any(s.section_key == "school_inputs" and (s.narrative_text or "").strip() for s in sections) else 0

    log_count = db.scalar(
        select(func.count(DailyLog.id))
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(TherapySession.case_id == report.case_id)
    ) or 0

    logs_with_notes = db.scalar(
        select(func.count(DailyLog.id))
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(TherapySession.case_id == report.case_id)
        .where(
            or_(
                func.length(func.trim(func.coalesce(DailyLog.observations, ""))) > 0,
                func.length(func.trim(func.coalesce(DailyLog.session_notes, ""))) > 0,
                func.length(func.trim(func.coalesce(DailyLog.activities_done, ""))) > 0,
                func.length(func.trim(func.coalesce(DailyLog.goals_addressed, ""))) > 0,
            )
        )
    ) or 0

    recent_rows = list(
        db.scalars(
            select(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(TherapySession.case_id == report.case_id)
            .options(selectinload(DailyLog.session))
            .order_by(TherapySession.scheduled_date.desc(), DailyLog.id.desc())
            .limit(5)
        ).all()
    )
    recent_sessions = []
    for log in recent_rows:
        sess = log.session
        snippet = _log_snippet(log)
        recent_sessions.append(
            {
                "log_id": log.id,
                "session_date": sess.scheduled_date.isoformat() if sess and sess.scheduled_date else None,
                "attendance": log.attendance_status,
                "snippet": snippet or "Session logged — narrative not added yet",
                "has_notes": _log_has_narrative(log),
            }
        )

    evidence_rows = list(
        db.scalars(select(ClinicalReportEvidence).where(ClinicalReportEvidence.report_id == report.id)).all()
    )
    uploads = sum(1 for e in evidence_rows if e.source_type == "uploaded_document")

    missing = []
    by_key = {s.section_key: s for s in sections}
    for key in REQUIRED_OBSERVATION_SECTION_KEYS:
        sec = by_key.get(key)
        if not sec or sec.completion_status != "completed":
            meta_label = sec.section_title if sec else key
            missing.append(meta_label)

    sources = [
        {
            "key": "session_logs",
            "label": "Session logs",
            "count": log_count,
            "detail": f"{logs_with_notes} with notes" if log_count else "No logs yet",
            "icon": "event_note",
        },
        {
            "key": "uploads",
            "label": "Uploaded files",
            "count": uploads,
            "detail": "Photos, PDFs, video",
            "icon": "folder_open",
        },
        {
            "key": "parent_inputs",
            "label": "Parent inputs",
            "count": parent_inputs,
            "detail": "Family observations",
            "icon": "family_restroom",
        },
        {
            "key": "school_inputs",
            "label": "School inputs",
            "count": school_inputs,
            "detail": "School team notes",
            "icon": "school",
        },
    ]

    return {
        "session_logs": log_count,
        "logs_with_notes": logs_with_notes,
        "completed_checklists": completed,
        "internal_notes": internal_notes,
        "evidence_uploads": uploads,
        "parent_inputs": parent_inputs,
        "school_inputs": school_inputs,
        "recent_sessions": recent_sessions,
        "sources": sources,
        "completion_pct": int(round(100 * completed / len(sections))) if sections else 0,
        "missing_required": missing,
        "submit_ready": len(missing) == 0,
    }
