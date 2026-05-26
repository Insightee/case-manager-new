from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clinical_constants import OBSERVATION_CHECKLIST_SECTIONS
from app.models.case import Case
from app.models.child import Child
from app.models.clinical import CaseClinicalProfile, ObservationChecklist, ObservationChecklistStatus
from app.models.report import ObservationReport, ReportCategory, ReportStatus
from app.models.review import ReviewDecision
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import case_service, notification_service
from app.services.report_service import review_observation_report

SHADOW_DUE_DAYS = 30
HOMECARE_COMPLETED_SESSIONS = 3


def _parse_responses(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) if v is not None else "" for k, v in data.items()}
    except json.JSONDecodeError:
        pass
    return {}


def _dump_responses(responses: dict[str, str]) -> str:
    return json.dumps({k: (v or "") for k, v in responses.items()})


def compute_due(case: Case, db: Session) -> tuple[date | None, str | None]:
    """Shadow: 30 days from case start; homecare: after 3 completed sessions."""
    start = case.created_at.date() if case.created_at else date.today()
    module = (case.product_module or "").lower()
    if module == "shadow_support" or "shadow" in (case.service_type or "").lower():
        return start + timedelta(days=SHADOW_DUE_DAYS), "shadow_30_days"
    completed = db.scalar(
        select(func.count(TherapySession.id)).where(
            TherapySession.case_id == case.id,
            TherapySession.status == SessionStatus.COMPLETED,
        )
    ) or 0
    if completed >= HOMECARE_COMPLETED_SESSIONS:
        return date.today(), "homecare_3_sessions"
    return None, "homecare_3_sessions_pending"


def get_or_create_profile(db: Session, case_id: int) -> CaseClinicalProfile:
    row = db.scalar(select(CaseClinicalProfile).where(CaseClinicalProfile.case_id == case_id))
    if row:
        return row
    row = CaseClinicalProfile(case_id=case_id)
    db.add(row)
    db.flush()
    return row


def profile_to_dict(profile: CaseClinicalProfile) -> dict:
    return {
        "case_id": profile.case_id,
        "history": profile.history,
        "diagnosis": profile.diagnosis,
        "strengths": profile.strengths,
        "interests": profile.interests,
        "goals_summary": profile.goals_summary,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def update_profile(db: Session, case: Case, user: User, payload: dict) -> CaseClinicalProfile:
    profile = get_or_create_profile(db, case.id)
    for key in ("history", "diagnosis", "strengths", "interests", "goals_summary"):
        if key in payload and payload[key] is not None:
            setattr(profile, key, payload[key])
    profile.updated_by_user_id = user.id
    db.flush()
    return profile


def get_or_create_checklist(db: Session, case: Case, therapist_user_id: int) -> ObservationChecklist:
    row = db.scalar(select(ObservationChecklist).where(ObservationChecklist.case_id == case.id))
    if row:
        return row
    due_at, due_rule = compute_due(case, db)
    row = ObservationChecklist(
        case_id=case.id,
        therapist_user_id=therapist_user_id,
        status=ObservationChecklistStatus.DRAFT.value,
        section_responses_json=_dump_responses({}),
        due_at=due_at,
        due_rule=due_rule,
    )
    db.add(row)
    db.flush()
    return row


def _checklist_permissions(checklist: ObservationChecklist, user: User, case: Case) -> tuple[bool, bool]:
    can_edit = checklist.status in (
        ObservationChecklistStatus.DRAFT.value,
        ObservationChecklistStatus.REJECTED.value,
    )
    if checklist.therapist_user_id != user.id:
        can_edit = False
    can_submit = can_edit and any(
        _parse_responses(checklist.section_responses_json).get(s["key"], "").strip()
        for s in OBSERVATION_CHECKLIST_SECTIONS
    )
    return can_edit, can_submit


def checklist_to_dict(db: Session, checklist: ObservationChecklist, case: Case, user: User) -> dict:
    due_at, due_rule = compute_due(case, db)
    if not checklist.due_at and due_at:
        checklist.due_at = due_at
        checklist.due_rule = due_rule
    today = date.today()
    is_due = bool(checklist.due_at and checklist.due_at <= today)
    is_overdue = bool(
        checklist.due_at
        and checklist.due_at < today
        and checklist.status
        in (ObservationChecklistStatus.DRAFT.value, ObservationChecklistStatus.REJECTED.value)
    )
    can_edit, can_submit = _checklist_permissions(checklist, user, case)
    return {
        "id": checklist.id,
        "case_id": checklist.case_id,
        "product_module": case.product_module,
        "therapist_user_id": checklist.therapist_user_id,
        "status": checklist.status,
        "sections": OBSERVATION_CHECKLIST_SECTIONS,
        "responses": _parse_responses(checklist.section_responses_json),
        "due_at": checklist.due_at.isoformat() if checklist.due_at else None,
        "due_rule": checklist.due_rule,
        "is_due": is_due,
        "is_overdue": is_overdue,
        "submitted_at": checklist.submitted_at.isoformat() if checklist.submitted_at else None,
        "reviewer_comment": checklist.reviewer_comment,
        "reviewed_at": checklist.reviewed_at.isoformat() if checklist.reviewed_at else None,
        "observation_report_id": checklist.observation_report_id,
        "can_edit": can_edit,
        "can_submit": can_submit,
    }


def save_checklist(
    db: Session,
    case: Case,
    user: User,
    responses: dict[str, str],
    *,
    sync_clinical_profile: bool = True,
) -> ObservationChecklist:
    checklist = get_or_create_checklist(db, case, user.id)
    if checklist.therapist_user_id != user.id:
        raise ValueError("Not authorized")
    if checklist.status not in (
        ObservationChecklistStatus.DRAFT.value,
        ObservationChecklistStatus.REJECTED.value,
    ):
        raise ValueError("Checklist cannot be edited in its current state")
    checklist.section_responses_json = _dump_responses(responses)
    if sync_clinical_profile:
        profile = get_or_create_profile(db, case.id)
        summary = responses.get("summary_recommendations", "").strip()
        referral = responses.get("referral_context", "").strip()
        if referral:
            profile.history = referral
        if summary:
            profile.goals_summary = summary
        profile.updated_by_user_id = user.id
    db.flush()
    return checklist


def submit_checklist(db: Session, case: Case, user: User) -> ObservationChecklist:
    checklist = get_or_create_checklist(db, case, user.id)
    if checklist.therapist_user_id != user.id:
        raise ValueError("Not authorized")
    if checklist.status not in (
        ObservationChecklistStatus.DRAFT.value,
        ObservationChecklistStatus.REJECTED.value,
    ):
        raise ValueError("Already submitted")
    responses = _parse_responses(checklist.section_responses_json)
    if not any(responses.get(s["key"], "").strip() for s in OBSERVATION_CHECKLIST_SECTIONS):
        raise ValueError("Complete at least one section before submitting")
    checklist.status = ObservationChecklistStatus.SUBMITTED.value
    checklist.submitted_at = datetime.now(timezone.utc)
    checklist.reviewer_comment = None
    db.flush()
    if case.case_manager_user_id:
        notification_service.create_notification(
            db,
            user_id=case.case_manager_user_id,
            title="Observation checklist submitted",
            body=f"Review checklist for {case.case_code}",
            entity_type="observation_checklist",
            entity_id=checklist.id,
        )
    return checklist


def _responses_to_html(responses: dict[str, str]) -> str:
    parts = []
    for section in OBSERVATION_CHECKLIST_SECTIONS:
        body = (responses.get(section["key"]) or "").strip()
        if not body:
            continue
        parts.append(f"<h3>{section['label']}</h3><p>{body.replace(chr(10), '<br/>')}</p>")
    return "".join(parts) or "<p>Observation checklist</p>"


def _responses_to_plain(responses: dict[str, str]) -> str:
    lines = []
    for section in OBSERVATION_CHECKLIST_SECTIONS:
        body = (responses.get(section["key"]) or "").strip()
        if body:
            lines.append(f"{section['label']}\n{body}")
    return "\n\n".join(lines)


def approve_checklist(
    db: Session,
    checklist: ObservationChecklist,
    reviewer: User,
    *,
    comment: str | None = None,
    share_with_parent: bool = True,
) -> ObservationChecklist:
    if checklist.status != ObservationChecklistStatus.SUBMITTED.value:
        raise ValueError("Checklist is not awaiting review")
    case = case_service.get_case(db, checklist.case_id)
    if not case:
        raise ValueError("Case not found")
    responses = _parse_responses(checklist.section_responses_json)
    body_html = _responses_to_html(responses)
    plain = _responses_to_plain(responses)
    child_name = case.child.full_name if case.child else "Child"
    title = f"Observation report — {child_name}"

    report = db.get(ObservationReport, checklist.observation_report_id) if checklist.observation_report_id else None
    if not report:
        report = ObservationReport(
            case_id=case.id,
            therapist_user_id=checklist.therapist_user_id,
            title=title,
            content=plain[:2000],
            body_html=body_html,
            category=ReportCategory.OBSERVATION.value,
            report_date=date.today(),
            status=ReportStatus.UNDER_REVIEW,
        )
        db.add(report)
        db.flush()
        checklist.observation_report_id = report.id
    else:
        report.title = title
        report.content = plain[:2000]
        report.body_html = body_html
        report.report_date = date.today()

    visibility = (
        VisibilityStatus.APPROVED_FOR_PARENT if share_with_parent else VisibilityStatus.INTERNAL_ONLY
    )
    review_observation_report(
        db,
        report,
        reviewer.id,
        decision=ReviewDecision.APPROVE,
        comment=comment,
        visibility=visibility,
    )
    checklist.status = ObservationChecklistStatus.APPROVED.value
    checklist.reviewed_by_user_id = reviewer.id
    checklist.reviewer_comment = comment
    checklist.reviewed_at = datetime.now(timezone.utc)
    profile = get_or_create_profile(db, case.id)
    referral = responses.get("referral_context", "").strip()
    summary = responses.get("summary_recommendations", "").strip()
    academic = responses.get("academic_learning", "").strip()
    social = responses.get("social_communication", "").strip()
    if referral:
        profile.history = referral
    if summary:
        profile.goals_summary = summary
    if academic:
        profile.diagnosis = profile.diagnosis or academic
    if social:
        profile.strengths = profile.strengths or social
    profile.updated_by_user_id = reviewer.id
    db.flush()
    notification_service.create_notification(
        db,
        user_id=checklist.therapist_user_id,
        title="Observation checklist approved",
        body=f"Your checklist for {case.case_code} was approved.",
        entity_type="observation_checklist",
        entity_id=checklist.id,
    )
    return checklist


def reject_checklist(
    db: Session,
    checklist: ObservationChecklist,
    reviewer: User,
    comment: str,
) -> ObservationChecklist:
    if checklist.status != ObservationChecklistStatus.SUBMITTED.value:
        raise ValueError("Checklist is not awaiting review")
    if not (comment or "").strip():
        raise ValueError("Reviewer comment is required")
    checklist.status = ObservationChecklistStatus.REJECTED.value
    checklist.reviewed_by_user_id = reviewer.id
    checklist.reviewer_comment = comment.strip()
    checklist.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    case = case_service.get_case(db, checklist.case_id)
    if case:
        notification_service.create_notification(
            db,
            user_id=checklist.therapist_user_id,
            title="Observation checklist needs changes",
            body=comment[:500],
            entity_type="observation_checklist",
            entity_id=checklist.id,
        )
    return checklist


def list_pending_for_admin(db: Session, user: User, *, limit: int = 50) -> list[dict]:
    from app.services.admin_scope_service import apply_case_scope

    stmt = (
        select(ObservationChecklist, Case, Child)
        .join(Case, ObservationChecklist.case_id == Case.id)
        .outerjoin(Child, Case.child_id == Child.id)
        .where(ObservationChecklist.status == ObservationChecklistStatus.SUBMITTED.value)
        .order_by(ObservationChecklist.submitted_at.asc())
        .limit(limit)
    )
    stmt = apply_case_scope(stmt, user)
    rows = db.execute(stmt).all()
    today = date.today()
    out = []
    for checklist, case, child in rows:
        therapist = db.get(User, checklist.therapist_user_id)
        child_name = " ".join(p for p in (child.first_name, child.last_name) if p).strip() if child else None
        out.append(
            {
                "id": checklist.id,
                "case_id": case.id,
                "case_code": case.case_code,
                "product_module": case.product_module,
                "child_name": child_name,
                "therapist_name": therapist.full_name if therapist else None,
                "status": checklist.status,
                "due_at": checklist.due_at.isoformat() if checklist.due_at else None,
                "submitted_at": checklist.submitted_at.isoformat() if checklist.submitted_at else None,
                "is_overdue": bool(checklist.due_at and checklist.due_at < today),
            }
        )
    return out
