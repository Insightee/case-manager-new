from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.clinical_report import (
    ClinicalReport,
    ClinicalReportReviewEvent,
    ClinicalReportSection,
    ClinicalReportStatus,
    ReviewEventType,
)
from app.models.user import User
from app.report_engine_constants import REPORT_TYPE_HOOKS


def _json_loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def log_review_event(
    db: Session,
    report: ClinicalReport,
    actor: User,
    event_type: str,
    *,
    comment: str | None = None,
    metadata: dict | None = None,
) -> None:
    role = actor.roles[0].name if getattr(actor, "roles", None) and actor.roles else None
    db.add(
        ClinicalReportReviewEvent(
            report_id=report.id,
            actor_id=actor.id,
            actor_role=role,
            event_type=event_type,
            comment=comment,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
    )


def can_therapist_edit(report: ClinicalReport, user: User) -> bool:
    if report.report_type == "iep" and report.status == ClinicalReportStatus.APPROVED.value:
        roles = {r.name for r in getattr(user, "roles", []) or []}
        if roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER"}:
            return True
        return report.assigned_therapist_id == user.id
    if report.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
        ClinicalReportStatus.ARCHIVED.value,
    ):
        return False
    if report.status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value:
        return False
    return report.assigned_therapist_id == user.id or report.created_by_id == user.id


def can_cm_review(report: ClinicalReport) -> bool:
    return report.status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value


def submit_report(db: Session, report: ClinicalReport, user: User, *, readiness_ok: bool) -> ClinicalReport:
    if not can_therapist_edit(report, user):
        raise ValueError("Cannot submit this report")
    if not readiness_ok:
        raise ValueError("Complete required sections before submitting")
    report.status = ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value
    report.submitted_at = datetime.now(timezone.utc)
    log_review_event(db, report, user, ReviewEventType.SUBMITTED.value)
    db.flush()
    return report


def return_report(db: Session, report: ClinicalReport, reviewer: User, comment: str) -> ClinicalReport:
    if not can_cm_review(report):
        raise ValueError("Report is not awaiting review")
    report.status = ClinicalReportStatus.RETURNED_FOR_CHANGES.value
    report.returned_at = datetime.now(timezone.utc)
    log_review_event(db, report, reviewer, ReviewEventType.RETURNED.value, comment=comment)
    db.flush()
    return report


def approve_report(db: Session, report: ClinicalReport, reviewer: User, *, share_parent: bool = False) -> ClinicalReport:
    if not can_cm_review(report):
        raise ValueError("Report is not awaiting review")
    now = datetime.now(timezone.utc)
    report.status = ClinicalReportStatus.APPROVED.value
    report.approved_at = now
    report.approved_by_id = reviewer.id
    if report.report_type != "iep":
        report.locked_at = now
        report.status = ClinicalReportStatus.LOCKED.value
    if share_parent:
        report.parent_visible_at = now
        log_review_event(db, report, reviewer, ReviewEventType.PARENT_SHARED.value)
    log_review_event(db, report, reviewer, ReviewEventType.APPROVED.value)
    if report.report_type != "iep":
        log_review_event(db, report, reviewer, ReviewEventType.LOCKED.value)
    else:
        from app.services import iep_report_service

        iep_report_service.sync_approved_iep_goals_to_active_case_plan(db, report, reviewer)
    db.flush()
    return report


def lock_report(db: Session, report: ClinicalReport, actor: User) -> ClinicalReport:
    report.status = ClinicalReportStatus.LOCKED.value
    report.locked_at = datetime.now(timezone.utc)
    log_review_event(db, report, actor, ReviewEventType.LOCKED.value)
    db.flush()
    return report


def report_type_hooks() -> dict:
    return REPORT_TYPE_HOOKS
