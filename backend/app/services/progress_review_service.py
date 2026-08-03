"""Progress report CM review workflow — return comments and review thread."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_report import ClinicalReport, ClinicalReportReviewEvent, ClinicalReportStatus
from app.models.user import User
from app.services import report_status_service


def _json_loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def list_review_thread(db: Session, report_id: int) -> list[dict]:
    rows = list(
        db.scalars(
            select(ClinicalReportReviewEvent)
            .where(ClinicalReportReviewEvent.report_id == report_id)
            .order_by(ClinicalReportReviewEvent.created_at.asc())
        ).all()
    )
    return [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "actor_role": r.actor_role,
            "event_type": r.event_type,
            "comment": r.comment,
            "metadata": _json_loads(r.metadata_json),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def return_with_comments(
    db: Session,
    report: ClinicalReport,
    reviewer: User,
    overall_note: str,
    *,
    section_comments: dict[str, str] | None = None,
) -> ClinicalReport:
    if report.report_type != "progress":
        raise ValueError("Not a progress report")
    metadata = {"section_comments": section_comments or {}}
    return report_status_service.return_report(db, report, reviewer, overall_note, metadata=metadata)


def resolve_returned_report(
    db: Session,
    report: ClinicalReport,
    therapist: User,
    *,
    resolutions: dict[str, str] | None = None,
) -> ClinicalReport:
    if report.status != ClinicalReportStatus.RETURNED_FOR_CHANGES.value:
        raise ValueError("Report is not returned for changes")
    if report.assigned_therapist_id != therapist.id:
        roles = {r.name for r in getattr(therapist, "roles", []) or []}
        if not roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER"}:
            raise ValueError("Only the assigned therapist can resolve returns")
    report_status_service.log_review_event(
        db,
        report,
        therapist,
        "return_resolved",
        metadata={"resolutions": resolutions or {}},
    )
    return report
