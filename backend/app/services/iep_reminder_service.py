"""IEP deadline reminders — in-app notifications + email for assigned therapists."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import today_ist
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus, ClinicalReportType
from app.models.notification import Notification
from app.models.user import User
from app.services import email_service, notification_service, report_engine_service

INITIAL_WINDOW_DAYS = 45
INITIAL_REMINDER_DAYS = (25, 35, 45)
RENEWAL_WINDOW_DAYS = 20
RENEWAL_REMINDER_DAYS = (5, 15, 20)

REMINDER_KINDS = {
    25: ("iep_start_draft", "IEP pending — start drafting"),
    35: ("iep_due_soon", "IEP due soon — submit for review"),
    45: ("iep_deadline", "IEP deadline today"),
    5: ("iep_renewal_start", "Next IEP — start drafting"),
    15: ("iep_renewal_due_soon", "Next IEP due soon"),
    20: ("iep_renewal_deadline", "Next IEP deadline today"),
}

ENTITY_TYPE = "iep_reminder"
_INCOMPLETE_STATUSES = {
    ClinicalReportStatus.DRAFT.value,
    ClinicalReportStatus.IN_PROGRESS.value,
    ClinicalReportStatus.RETURNED_FOR_CHANGES.value,
    ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value,
}
_COMPLETE_STATUSES = {
    ClinicalReportStatus.APPROVED.value,
    ClinicalReportStatus.LOCKED.value,
}


def _active_assignment(db: Session, case_id: int, therapist_user_id: int) -> CaseAssignment | None:
    return db.scalar(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        ).order_by(CaseAssignment.start_date.desc())
    )


def _latest_approved_iep(db: Session, case_id: int) -> ClinicalReport | None:
    return db.scalar(
        select(ClinicalReport).where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.IEP.value,
            ClinicalReport.status.in_(_COMPLETE_STATUSES),
        ).order_by(ClinicalReport.approved_at.desc().nullslast(), ClinicalReport.id.desc())
    )


def _active_iep(db: Session, case_id: int) -> ClinicalReport | None:
    return report_engine_service.get_active_iep_report(db, case_id)


def _review_date_from_report(db: Session, report: ClinicalReport) -> date | None:
    from app.models.clinical_report import ClinicalReportSection

    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "review_parent_plan",
        )
    )
    if not sec or not sec.structured_data_json:
        return None
    import json

    data = json.loads(sec.structured_data_json) if isinstance(sec.structured_data_json, str) else sec.structured_data_json
    raw = (data or {}).get("review_date")
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _iep_is_complete(report: ClinicalReport | None) -> bool:
    return bool(report and report.status in _COMPLETE_STATUSES)


def _iep_needs_work(report: ClinicalReport | None) -> bool:
    if not report:
        return True
    return report.status in _INCOMPLETE_STATUSES


def compute_deadline_state(
    db: Session,
    case: Case,
    therapist_user_id: int,
    *,
    on_date: date | None = None,
) -> dict[str, Any] | None:
    """Return active IEP deadline context for a case/therapist, or None if no reminder applies."""
    today = on_date or today_ist()
    assignment = _active_assignment(db, case.id, therapist_user_id)
    if not assignment:
        return None

    active_iep = _active_iep(db, case.id)
    approved = _latest_approved_iep(db, case.id)
    review_date = _review_date_from_approved(db, approved) if approved else None

    renewal_due = bool(approved and review_date and today >= review_date)
    renewal_in_progress = bool(active_iep and active_iep.status in _INCOMPLETE_STATUSES)
    initial_needed = not approved

    if renewal_due and (renewal_in_progress or _iep_is_complete(active_iep) or not active_iep):
        window_start = review_date
        cycle = "renewal"
        window_days = RENEWAL_WINDOW_DAYS
        reminder_days = RENEWAL_REMINDER_DAYS
        if active_iep and active_iep.status in _COMPLETE_STATUSES:
            pass
    elif initial_needed and _iep_needs_work(active_iep):
        window_start = assignment.start_date
        cycle = "initial"
        window_days = INITIAL_WINDOW_DAYS
        reminder_days = INITIAL_REMINDER_DAYS
    else:
        return None

    day_in_window = (today - window_start).days + 1
    if day_in_window < 1 or day_in_window > window_days:
        return None

    if cycle == "initial" and active_iep and active_iep.status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value:
        return None
    if cycle == "renewal" and active_iep and active_iep.status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value:
        return None

    applicable = [d for d in reminder_days if day_in_window >= d]
    if not applicable:
        return None
    current_day = max(applicable)

    kind, title = REMINDER_KINDS[current_day]
    child_name = case.child.full_name if case.child else "Client"
    if current_day == 25:
        body = f"IEP pending for {child_name} ({case.case_code}). Please start drafting your IEP."
    elif current_day == 35:
        body = f"Your IEP for {child_name} ({case.case_code}) is due — please submit it for review."
    elif current_day == 45:
        body = f"Today is the deadline for IEP submission for {child_name} ({case.case_code}). Please submit the IEP."
    elif current_day == 5:
        body = f"Review date reached for {child_name} ({case.case_code}). Please start drafting the next IEP."
    elif current_day == 15:
        body = f"Your next IEP for {child_name} ({case.case_code}) is due soon — please submit for review."
    else:
        body = f"Today is the deadline for the next IEP for {child_name} ({case.case_code}). Please submit the IEP."

    return {
        "case_id": case.id,
        "case_code": case.case_code,
        "child_name": child_name,
        "cycle": cycle,
        "day_in_window": day_in_window,
        "window_start": window_start.isoformat(),
        "window_days": window_days,
        "reminder_kind": kind,
        "title": title,
        "body": body,
        "dedupe_key": f"{kind}:{cycle}:{window_start.isoformat()}",
        "report_id": active_iep.id if active_iep else None,
    }


def _review_date_from_approved(db: Session, report: ClinicalReport | None) -> date | None:
    if not report:
        return None
    return _review_date_from_report(db, report)


def _therapist_for_case(db: Session, case_id: int) -> User | None:
    assignment = db.scalar(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        ).order_by(CaseAssignment.start_date.desc())
    )
    if not assignment:
        return None
    return db.get(User, assignment.therapist_user_id)


def _iep_builder_url(case_id: int) -> str:
    base = (settings.frontend_url or "").rstrip("/")
    return f"{base}/therapist/cases/{case_id}/reports/iep"


def _notify_therapist(
    db: Session,
    therapist: User,
    case: Case,
    state: dict[str, Any],
) -> bool:
    dedupe = state["dedupe_key"]
    existing = db.scalar(
        select(Notification).where(
            Notification.user_id == therapist.id,
            Notification.entity_type == ENTITY_TYPE,
            Notification.entity_id == case.id,
            Notification.body.like(f"%[{dedupe}]%"),
        )
    )
    if existing:
        return False

    notification_service.create_notification(
        db,
        user_id=therapist.id,
        title=state["title"],
        body=state["body"],
        entity_type=ENTITY_TYPE,
        entity_id=case.id,
        dedupe_key=dedupe,
    )
    if therapist.email:
        email_service.send_email(
            to=therapist.email,
            subject=state["title"],
            body_text=f"{state['body']}\n\nOpen IEP builder: {_iep_builder_url(case.id)}\n",
        )
    return True


def send_due_iep_reminders(db: Session, *, on_date: date | None = None, dry_run: bool = False) -> dict[str, int]:
    today = on_date or today_ist()
    sent = 0
    scanned = 0
    assignments = db.scalars(
        select(CaseAssignment).where(CaseAssignment.status == CaseAssignmentStatus.ACTIVE)
    ).all()
    seen: set[tuple[int, int]] = set()
    for assignment in assignments:
        key = (assignment.case_id, assignment.therapist_user_id)
        if key in seen:
            continue
        seen.add(key)
        case = db.get(Case, assignment.case_id)
        therapist = db.get(User, assignment.therapist_user_id)
        if not case or not therapist:
            continue
        scanned += 1
        state = compute_deadline_state(db, case, therapist.id, on_date=today)
        if not state:
            continue
        if dry_run:
            sent += 1
            continue
        if _notify_therapist(db, therapist, case, state):
            sent += 1
    return {"scanned": scanned, "sent": sent}


def list_active_reminders_for_therapist(db: Session, user_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.entity_type == ENTITY_TYPE,
            Notification.is_read.is_(False),
        ).order_by(Notification.created_at.desc())
    ).all()
    out: list[dict[str, Any]] = []
    for n in rows:
        case = db.get(Case, n.entity_id) if n.entity_id else None
        out.append(
            {
                "notification_id": n.id,
                "case_id": n.entity_id,
                "case_code": case.case_code if case else None,
                "child_name": case.child.full_name if case and case.child else None,
                "title": n.title,
                "body": n.body.replace(n.body.split("]")[0] + "] ", "") if n.body.startswith("[") else n.body,
                "href": f"/therapist/cases/{n.entity_id}/reports/iep" if n.entity_id else "/therapist/reports",
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
        )
    return out


def acknowledge_reminders_for_case(db: Session, user_id: int, case_id: int) -> int:
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.entity_type == ENTITY_TYPE,
            Notification.entity_id == case_id,
            Notification.is_read.is_(False),
        )
    ).all()
    count = 0
    for n in rows:
        n.is_read = True
        count += 1
    db.flush()
    return count


def prompt_renew_iep(db: Session, case: Case, cm_user: User) -> dict[str, Any]:
    """CM action — notify assigned therapist to start the next IEP cycle."""
    therapist = _therapist_for_case(db, case.id)
    if not therapist:
        raise ValueError("No active therapist assigned to this case.")
    child_name = case.child.full_name if case.child else "Client"
    title = "Start next IEP"
    body = f"Your case manager requested you start the next IEP for {child_name} ({case.case_code})."
    dedupe = f"renew_prompt:{today_ist().isoformat()}"
    notification_service.create_notification(
        db,
        user_id=therapist.id,
        title=title,
        body=body,
        entity_type=ENTITY_TYPE,
        entity_id=case.id,
        dedupe_key=dedupe,
    )
    if therapist.email:
        email_service.send_email(
            to=therapist.email,
            subject=title,
            body_text=f"{body}\n\nOpen IEP builder: {_iep_builder_url(case.id)}\n",
        )
    return {"ok": True, "therapist_user_id": therapist.id, "case_id": case.id}


def list_iep_versions_for_case(db: Session, case_id: int) -> list[dict[str, Any]]:
    reports = db.scalars(
        select(ClinicalReport).where(
            ClinicalReport.case_id == case_id,
            ClinicalReport.report_type == ClinicalReportType.IEP.value,
        ).order_by(ClinicalReport.created_at.desc())
    ).all()
    out = []
    for r in reports:
        created = r.created_at
        period_label = created.strftime("%B %Y") if created else "Unknown"
        out.append(
            {
                "report_id": r.id,
                "status": r.status,
                "period_label": period_label,
                "created_at": created.isoformat() if created else None,
                "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                "archived": r.archived_at is not None,
                "is_active": r.archived_at is None,
            }
        )
    return out


def iep_period_label(report: ClinicalReport) -> str:
    if report.created_at:
        return report.created_at.strftime("%B %Y")
    return "Unknown"
