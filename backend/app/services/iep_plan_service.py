from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment
from app.models.case import Case
from app.models.child import Child
from app.models.iep_plan import IepPlan, IepPlanStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.schemas.iep_plan import IepPlanSections, LearningEnvironmentRow
from app.services import case_service, notification_service
from app.services.observation_checklist_service import get_or_create_profile, _parse_responses
from app.models.clinical import ObservationChecklist, ObservationChecklistStatus

DEFAULT_SECTIONS = IepPlanSections()


def _parse_sections(raw: str | None) -> IepPlanSections:
    if not raw:
        return DEFAULT_SECTIONS.model_copy(deep=True)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            env_rows = data.get("learning_environments") or []
            if env_rows and isinstance(env_rows[0], dict):
                data["learning_environments"] = [LearningEnvironmentRow(**r) for r in env_rows]
            return IepPlanSections.model_validate(data)
    except Exception:
        pass
    return DEFAULT_SECTIONS.model_copy(deep=True)


def _dump_sections(sections: IepPlanSections) -> str:
    return sections.model_dump_json()


def observation_text_for_case(db: Session, case_id: int) -> str:
    """Pull approved checklist or clinical profile text for IEP prefill."""
    checklist = db.scalar(select(ObservationChecklist).where(ObservationChecklist.case_id == case_id))
    if checklist and checklist.status == ObservationChecklistStatus.APPROVED.value:
        responses = _parse_responses(checklist.section_responses_json)
        parts = [
            responses.get(k, "").strip()
            for k in ("summary_recommendations", "referral_context", "academic_learning")
        ]
        text = "\n\n".join(p for p in parts if p)
        if text:
            return text
    from app.models.clinical import CaseClinicalProfile

    profile = db.scalar(select(CaseClinicalProfile).where(CaseClinicalProfile.case_id == case_id))
    if profile:
        chunks = [profile.history, profile.diagnosis, profile.goals_summary]
        return "\n\n".join(c for c in chunks if c)
    return ""


def _prefill_sections(db: Session, case: Case) -> IepPlanSections:
    sections = DEFAULT_SECTIONS.model_copy(deep=True)
    child = case.child
    if child:
        sections.about_child = f"{child.full_name}"
        if child.date_of_birth:
            sections.about_child += f" (DOB: {child.date_of_birth})"
    profile = get_or_create_profile(db, case.id)
    if profile.history:
        sections.referral = profile.history
    if profile.diagnosis:
        sections.about_child += f"\n\nDiagnosis notes: {profile.diagnosis}"
    obs = observation_text_for_case(db, case.id)
    if obs:
        sections.observations = obs
    if not sections.learning_environments:
        sections.learning_environments = [
            LearningEnvironmentRow(environment="Home", strengths="", supports_needed=""),
            LearningEnvironmentRow(environment="School", strengths="", supports_needed=""),
        ]
    return sections


def get_latest_plan(db: Session, case_id: int) -> IepPlan | None:
    return db.scalar(
        select(IepPlan)
        .where(IepPlan.case_id == case_id)
        .order_by(IepPlan.id.desc())
        .limit(1)
    )


def plan_to_dict(db: Session, plan: IepPlan, user: User) -> dict:
    can_edit = plan.status in (IepPlanStatus.DRAFT.value, IepPlanStatus.INTERNAL_REVIEW.value)
    can_share = plan.status != IepPlanStatus.SHARED_WITH_PARENT.value
    return {
        "id": plan.id,
        "case_id": plan.case_id,
        "version": plan.version,
        "status": plan.status,
        "visibility_status": plan.visibility_status,
        "sections": _parse_sections(plan.sections_json).model_dump(),
        "attachment_id": plan.attachment_id,
        "created_by_user_id": plan.created_by_user_id,
        "published_at": plan.published_at.isoformat() if plan.published_at else None,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "can_edit": can_edit,
        "can_share_with_parent": can_share,
    }


def get_or_create_plan(db: Session, case: Case, user: User) -> IepPlan:
    plan = get_latest_plan(db, case.id)
    if plan:
        return plan
    sections = _prefill_sections(db, case)
    plan = IepPlan(
        case_id=case.id,
        version="v1",
        status=IepPlanStatus.DRAFT.value,
        sections_json=_dump_sections(sections),
        visibility_status=VisibilityStatus.INTERNAL_ONLY.value,
        created_by_user_id=user.id,
    )
    db.add(plan)
    db.flush()
    return plan


def save_plan(db: Session, plan: IepPlan, sections: IepPlanSections, version: str | None = None) -> IepPlan:
    if plan.status == IepPlanStatus.SHARED_WITH_PARENT.value:
        raise ValueError("Published IEP cannot be edited; create a new version")
    plan.sections_json = _dump_sections(sections)
    if version:
        plan.version = version
    plan.status = IepPlanStatus.DRAFT.value
    db.flush()
    return plan


def _sections_to_html(sections: IepPlanSections) -> str:
    parts = []
    if sections.about_child.strip():
        parts.append(f"<h2>About the child</h2><p>{sections.about_child.replace(chr(10), '<br/>')}</p>")
    if sections.referral.strip():
        parts.append(f"<h2>Referral</h2><p>{sections.referral.replace(chr(10), '<br/>')}</p>")
    if sections.observations.strip():
        parts.append(f"<h2>Observations</h2><p>{sections.observations.replace(chr(10), '<br/>')}</p>")
    if sections.learning_environments:
        rows = "".join(
            f"<tr><td>{r.environment}</td><td>{r.strengths}</td><td>{r.supports_needed}</td></tr>"
            for r in sections.learning_environments
            if r.environment or r.strengths or r.supports_needed
        )
        if rows:
            parts.append(
                "<h2>Learning environments</h2><table border='1' cellpadding='6'>"
                "<tr><th>Environment</th><th>Strengths</th><th>Supports needed</th></tr>"
                f"{rows}</table>"
            )
    if sections.interventions.strip():
        parts.append(f"<h2>Interventions</h2><p>{sections.interventions.replace(chr(10), '<br/>')}</p>")
    if sections.signatures.strip():
        parts.append(f"<h2>Signatures</h2><p>{sections.signatures.replace(chr(10), '<br/>')}</p>")
    return "".join(parts) or "<p>IEP plan</p>"


def share_plan_with_parent(db: Session, plan: IepPlan, user: User) -> IepPlan:
    case = case_service.get_case(db, plan.case_id)
    if not case:
        raise ValueError("Case not found")
    sections = _parse_sections(plan.sections_json)
    html = _sections_to_html(sections)
    att = None
    if plan.attachment_id:
        att = db.get(Attachment, plan.attachment_id)
    if not att:
        upload_dir = Path("uploads/iep")
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"iep_plan_{plan.case_id}_{plan.id}.html"
        file_path = str(upload_dir / safe_name)
        Path(file_path).write_text(html, encoding="utf-8")
        att = Attachment(
            case_id=case.id,
            entity_type="iep",
            entity_id=plan.id,
            file_name=f"IEP_{case.case_code}_{plan.version}.html",
            file_path=file_path,
            version=plan.version,
            visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
            uploaded_by_user_id=user.id,
        )
        db.add(att)
        db.flush()
        plan.attachment_id = att.id
    else:
        att.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
        Path(att.file_path).write_text(html, encoding="utf-8")
    plan.status = IepPlanStatus.SHARED_WITH_PARENT.value
    plan.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT.value
    plan.published_at = datetime.now(timezone.utc)
    db.flush()
    from app.models.parent import ParentGuardian, parent_child_link

    rows = db.execute(
        select(ParentGuardian.user_id)
        .select_from(parent_child_link)
        .join(ParentGuardian, parent_child_link.c.parent_guardian_id == ParentGuardian.id)
        .where(parent_child_link.c.child_id == case.child_id)
    ).all()
    for (uid,) in rows:
        if uid:
            notification_service.create_notification(
                db,
                user_id=uid,
                title="New IEP plan shared",
                body=f"IEP {plan.version} for {case.case_code} is ready for your review.",
                entity_type="iep",
                entity_id=att.id,
            )
    return plan


def list_plans_scoped(
    db: Session,
    user,
    *,
    status=None,
    limit: int = 50,
) -> list[dict]:
    from app.services.admin_scope_service import apply_case_scope

    stmt = (
        select(IepPlan, Case, Child)
        .join(Case, IepPlan.case_id == Case.id)
        .outerjoin(Child, Case.child_id == Child.id)
        .order_by(IepPlan.updated_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(IepPlan.status == status)
    stmt = apply_case_scope(stmt, user)
    rows = db.execute(stmt).all()
    return [
        {
            "id": p.id,
            "case_id": p.case_id,
            "case_code": case.case_code if case else None,
            "child_name": child.full_name if child else None,
            "version": p.version,
            "status": p.status,
            "visibility_status": p.visibility_status,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p, case, child in rows
    ]


def list_plans_for_case(db: Session, case_id: int) -> list[dict]:
    rows = db.scalars(select(IepPlan).where(IepPlan.case_id == case_id).order_by(IepPlan.id.desc())).all()
    case = case_service.get_case(db, case_id)
    child_name = case.child.full_name if case and case.child else None
    return [
        {
            "id": p.id,
            "case_id": p.case_id,
            "case_code": case.case_code if case else None,
            "child_name": child_name,
            "version": p.version,
            "status": p.status,
            "visibility_status": p.visibility_status,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in rows
    ]
