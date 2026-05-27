from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.attachment import Attachment
from app.models.case import Case
from app.models.child import Child
from app.models.iep_plan import IepPlan, IepPlanStatus
from app.models.iep_plan_suggestion import IepPlanSuggestion
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.schemas.iep_plan import (
    IepGoalStrategyBlock,
    IepHeaderSection,
    IepLearningStyleSection,
    IepPerformanceDomain,
    IepPlanSections,
    IepVerificationSection,
    LearningEnvironmentRow,
    PERFORMANCE_DOMAINS,
)
from app.services import case_service, notification_service
from app.services.observation_checklist_service import get_or_create_profile, _parse_responses
from app.models.clinical import ObservationChecklist, ObservationChecklistStatus

DEFAULT_SECTIONS = IepPlanSections()
EDITABLE_STATUSES = frozenset(
    {
        IepPlanStatus.DRAFT.value,
        IepPlanStatus.INTERNAL_REVIEW.value,
        IepPlanStatus.EDITS_SUGGESTED.value,
    }
)

REVISABLE_STATUSES = frozenset(
    {
        IepPlanStatus.SHARED_WITH_PARENT.value,
        IepPlanStatus.PARENT_ACKNOWLEDGED.value,
        IepPlanStatus.APPROVED.value,
    }
)

IEP_DOC_TABLE_STYLE = (
    "<style>.iep-doc-table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}"
    ".iep-doc-table th,.iep-doc-table td{border:1px solid #cbd5e1;padding:8px;text-align:left;vertical-align:top}"
    ".iep-doc-table th{background:#f1f5f9;font-weight:600}"
    ".iep-doc-table tr:nth-child(even){background:#f8fafc}"
    ".iep-doc-section{margin-bottom:20px}</style>"
)


def _age_label(dob: date | None) -> str:
    if not dob:
        return ""
    today = date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return f"{years} years old"


def _migrate_v1_sections(data: dict) -> dict:
    if data.get("schema_version", 1) >= 2 and data.get("header"):
        return data
    header = IepHeaderSection(
        about_child_brief=data.get("about_child") or "",
    )
    challenges = data.get("challenges") or data.get("referral") or ""
    verification = IepVerificationSection()
    if data.get("signatures"):
        verification.therapist_name = str(data.get("signatures", ""))[:200]
    env_rows = []
    for r in data.get("learning_environments") or []:
        if isinstance(r, dict):
            env_rows.append(
                LearningEnvironmentRow(
                    environment=r.get("environment", ""),
                    strengths=r.get("strengths", ""),
                    goals=r.get("goals", ""),
                    strategies=r.get("strategies", ""),
                    supports_needed=r.get("supports_needed", ""),
                )
            )
    perf = [
        IepPerformanceDomain(domain=d, notes="")
        for d in PERFORMANCE_DOMAINS
    ]
    return {
        "schema_version": 2,
        "header": header.model_dump(),
        "observations": data.get("observations") or "",
        "learning_environments": [e.model_dump() for e in env_rows],
        "challenges": challenges,
        "current_performance": [p.model_dump() for p in perf],
        "learning_style": IepLearningStyleSection().model_dump(),
        "interventions": data.get("interventions") or "",
        "talent_development": IepGoalStrategyBlock().model_dump(),
        "other_areas_of_need": IepGoalStrategyBlock().model_dump(),
        "intervention_by_insighte": "",
        "verification": verification.model_dump(),
        "supplementary_attachment_ids": data.get("supplementary_attachment_ids") or [],
        "about_child": data.get("about_child") or "",
        "referral": data.get("referral") or "",
        "signatures": data.get("signatures") or "",
    }


def _parse_sections(raw: str | None) -> IepPlanSections:
    if not raw:
        return DEFAULT_SECTIONS.model_copy(deep=True)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            data = _migrate_v1_sections(data)
            return IepPlanSections.model_validate(data)
    except Exception:
        pass
    return DEFAULT_SECTIONS.model_copy(deep=True)


def _dump_sections(sections: IepPlanSections) -> str:
    if not sections.schema_version:
        sections.schema_version = 2
    return sections.model_dump_json()


def observation_text_for_case(db: Session, case_id: int) -> str:
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


def _parent_names_for_child(db: Session, child_id: int) -> str:
    from app.models.parent import ParentGuardian, parent_child_link

    rows = db.execute(
        select(User.full_name)
        .select_from(parent_child_link)
        .join(ParentGuardian, parent_child_link.c.parent_guardian_id == ParentGuardian.id)
        .join(User, ParentGuardian.user_id == User.id)
        .where(parent_child_link.c.child_id == child_id)
    ).all()
    names = [n for (n,) in rows if n]
    return " and ".join(names)


def _active_therapist_name(db: Session, case_id: int) -> tuple[str, str]:
    row = db.execute(
        select(User, TherapistProfile.license_number)
        .select_from(CaseAssignment)
        .join(User, CaseAssignment.therapist_user_id == User.id)
        .outerjoin(TherapistProfile, TherapistProfile.user_id == User.id)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
        .limit(1)
    ).first()
    if not row:
        return "", ""
    therapist, license_no = row
    return therapist.full_name or "", license_no or ""


def _user_role_name(user: User) -> str:
    if getattr(user, "role_name", None):
        return str(user.role_name)
    if user.roles:
        return user.roles[0].name
    return ""


def _bump_version_label(version: str) -> str:
    m = re.match(r"^v(\d+)$", (version or "v1").strip(), re.IGNORECASE)
    if m:
        return f"v{int(m.group(1)) + 1}"
    return "v2"


def _sync_verification(sections: IepPlanSections, user: User, case: Case, db: Session) -> None:
    ctx = build_case_context(db, case)
    v = sections.verification
    v.therapist_name = ctx.get("therapist_name") or ""
    v.therapist_license_no = ctx.get("therapist_license_no") or ""
    v.case_manager_name = ctx.get("case_manager_name") or ""
    if not v.case_manager_date:
        v.case_manager_date = date.today().isoformat()
    role = _user_role_name(user)
    if v.therapist_verified:
        v.prepared_by_user_id = user.id
        v.prepared_by_name = user.full_name or ""
        v.prepared_by_role = role
        v.prepared_at = date.today().isoformat()
        if role == "THERAPIST":
            v.therapist_date = v.prepared_at
    elif v.prepared_by_user_id == user.id:
        v.prepared_by_user_id = None
        v.prepared_by_name = ""
        v.prepared_by_role = ""
        v.prepared_at = None


def validate_sections_for_share(sections: IepPlanSections) -> list[str]:
    errors: list[str] = []
    if not (sections.header.child_name or "").strip():
        errors.append("Child name is required in the header.")
    has_content = False
    if (sections.observations or "").strip():
        has_content = True
    for row in sections.learning_environments or []:
        if any(
            (getattr(row, f, "") or "").strip()
            for f in ("goals", "strategies", "supports_needed", "strengths", "environment")
        ):
            has_content = True
            break
    if not has_content:
        for perf in sections.current_performance or []:
            if (perf.notes or "").strip():
                has_content = True
                break
    td = sections.talent_development
    other = sections.other_areas_of_need
    if any(
        (x or "").strip()
        for x in (
            td.strengths,
            td.goals,
            td.strategies,
            other.areas_of_need,
            other.goals,
            other.strategies,
            sections.interventions,
            sections.intervention_by_insighte,
            sections.challenges,
        )
    ):
        has_content = True
    if not has_content:
        errors.append("Add clinical or goals content before sharing (observations, environments, or goals).")
    v = sections.verification
    verified = (v.prepared_by_name or "").strip() or (
        v.therapist_verified and (v.therapist_name or "").strip()
    )
    if not verified:
        errors.append("Check “I verify this document” on the Verification tab before sharing.")
    return errors


def _plan_for_attachment(db: Session, att: Attachment) -> IepPlan | None:
    plan = db.scalar(
        select(IepPlan).where(IepPlan.attachment_id == att.id).order_by(IepPlan.id.desc()).limit(1)
    )
    if not plan and att.entity_id:
        plan = db.get(IepPlan, att.entity_id)
    return plan


def build_case_context(db: Session, case: Case) -> dict:
    child = case.child
    profile = get_or_create_profile(db, case.id)
    therapist_name, license_no = _active_therapist_name(db, case.id)
    cm_name = ""
    if case.case_manager_user_id:
        cm = db.get(User, case.case_manager_user_id)
        cm_name = cm.full_name if cm else ""
    return {
        "child_name": child.full_name if child else "",
        "age_label": _age_label(child.date_of_birth if child else None),
        "diagnosis": profile.diagnosis or "",
        "service_provided": f"{case.service_type} ({case.product_module})",
        "parents_names": _parent_names_for_child(db, child.id) if child else "",
        "therapist_name": therapist_name,
        "therapist_license_no": license_no,
        "case_manager_name": cm_name,
        "case_code": case.case_code,
        "product_module": case.product_module,
    }


def _prefill_sections(db: Session, case: Case, user: User) -> IepPlanSections:
    sections = DEFAULT_SECTIONS.model_copy(deep=True)
    ctx = build_case_context(db, case)
    sections.header = IepHeaderSection(
        child_name=ctx["child_name"],
        age_label=ctx["age_label"],
        diagnosis=ctx["diagnosis"],
        service_provided=ctx["service_provided"],
        parents_names=ctx["parents_names"],
        therapist_name=ctx["therapist_name"],
        about_child_brief=profile_brief(db, case),
    )
    profile = get_or_create_profile(db, case.id)
    if profile.history:
        sections.challenges = profile.history
    obs = observation_text_for_case(db, case.id)
    if obs:
        sections.observations = obs
    sections.verification.therapist_name = ctx["therapist_name"]
    sections.verification.therapist_license_no = ctx["therapist_license_no"]
    sections.verification.case_manager_name = ctx["case_manager_name"]
    sections.verification.case_manager_date = date.today().isoformat()
    if not sections.learning_environments:
        sections.learning_environments = [
            LearningEnvironmentRow(environment="Home"),
            LearningEnvironmentRow(environment="School"),
        ]
    sections.current_performance = [IepPerformanceDomain(domain=d) for d in PERFORMANCE_DOMAINS]
    return sections


def profile_brief(db: Session, case: Case) -> str:
    profile = get_or_create_profile(db, case.id)
    parts = [profile.strengths, profile.interests, profile.goals_summary]
    return "\n\n".join(p for p in parts if p)


def get_latest_plan(db: Session, case_id: int) -> IepPlan | None:
    return db.scalar(
        select(IepPlan).where(IepPlan.case_id == case_id).order_by(IepPlan.id.desc()).limit(1)
    )


def _list_suggestions(db: Session, plan_id: int) -> list[dict]:
    rows = db.scalars(
        select(IepPlanSuggestion)
        .where(IepPlanSuggestion.iep_plan_id == plan_id)
        .order_by(IepPlanSuggestion.created_at.desc())
    ).all()
    out = []
    for s in rows:
        author = db.get(User, s.author_user_id)
        out.append(
            {
                "id": s.id,
                "author_user_id": s.author_user_id,
                "author_role": s.author_role,
                "author_name": author.full_name if author else None,
                "body": s.body,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "resolved_at": s.resolved_at.isoformat() if s.resolved_at else None,
            }
        )
    return out


def plan_to_dict(db: Session, plan: IepPlan, user: User, *, include_context: bool = True) -> dict:
    can_edit = plan.status in EDITABLE_STATUSES
    can_share = plan.status not in (
        IepPlanStatus.SHARED_WITH_PARENT.value,
        IepPlanStatus.PARENT_ACKNOWLEDGED.value,
        IepPlanStatus.APPROVED.value,
    )
    latest = get_latest_plan(db, plan.case_id)
    can_create_revision = bool(
        latest
        and latest.id == plan.id
        and plan.status in REVISABLE_STATUSES
    )
    case = case_service.get_case(db, plan.case_id)
    ctx = build_case_context(db, case) if case and include_context else None
    sections = _parse_sections(plan.sections_json)
    if case and include_context:
        _sync_verification(sections, user, case, db)
    return {
        "id": plan.id,
        "case_id": plan.case_id,
        "version": plan.version,
        "status": plan.status,
        "visibility_status": plan.visibility_status,
        "sections": sections.model_dump(),
        "case_context": ctx,
        "suggestions": _list_suggestions(db, plan.id),
        "attachment_id": plan.attachment_id,
        "created_by_user_id": plan.created_by_user_id,
        "published_at": plan.published_at.isoformat() if plan.published_at else None,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "can_edit": can_edit,
        "can_share_with_parent": can_share,
        "can_create_revision": can_create_revision,
    }


def get_or_create_plan(db: Session, case: Case, user: User) -> IepPlan:
    plan = get_latest_plan(db, case.id)
    if plan:
        return plan
    sections = _prefill_sections(db, case, user)
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


def save_plan(
    db: Session,
    plan: IepPlan,
    sections: IepPlanSections,
    user: User,
    version: str | None = None,
) -> IepPlan:
    if plan.status in (
        IepPlanStatus.APPROVED.value,
        IepPlanStatus.SHARED_WITH_PARENT.value,
        IepPlanStatus.PARENT_ACKNOWLEDGED.value,
    ):
        raise ValueError("This IEP version cannot be edited; create a new version")
    case = case_service.get_case(db, plan.case_id)
    if case:
        _sync_verification(sections, user, case, db)
    plan.sections_json = _dump_sections(sections)
    if version:
        plan.version = version
    if plan.status == IepPlanStatus.INTERNAL_REVIEW.value:
        pass
    elif plan.status == IepPlanStatus.EDITS_SUGGESTED.value:
        plan.status = IepPlanStatus.DRAFT.value
    else:
        published_sibling = db.scalar(
            select(IepPlan.id)
            .where(
                IepPlan.case_id == plan.case_id,
                IepPlan.id != plan.id,
                IepPlan.status.in_(tuple(REVISABLE_STATUSES)),
            )
            .limit(1)
        )
        if published_sibling:
            plan.status = IepPlanStatus.INTERNAL_REVIEW.value
        else:
            plan.status = IepPlanStatus.DRAFT.value
    db.flush()
    return plan


def create_new_version(db: Session, case: Case, user: User) -> IepPlan:
    latest = get_latest_plan(db, case.id)
    if not latest:
        raise ValueError("No IEP plan exists for this case")
    if latest.status in EDITABLE_STATUSES:
        return latest
    if latest.status not in REVISABLE_STATUSES:
        raise ValueError("Current IEP cannot be revised")
    sections = _parse_sections(latest.sections_json)
    plan = IepPlan(
        case_id=case.id,
        version=_bump_version_label(latest.version),
        status=IepPlanStatus.DRAFT.value,
        sections_json=_dump_sections(sections),
        visibility_status=VisibilityStatus.INTERNAL_ONLY.value,
        created_by_user_id=user.id,
    )
    db.add(plan)
    db.flush()
    return plan


def add_suggestion(db: Session, plan: IepPlan, user: User, role: str, body: str) -> IepPlanSuggestion:
    body = (body or "").strip()
    if not body:
        raise ValueError("Suggestion text is required")
    row = IepPlanSuggestion(
        iep_plan_id=plan.id,
        author_user_id=user.id,
        author_role=role,
        body=body,
    )
    db.add(row)
    plan.status = IepPlanStatus.EDITS_SUGGESTED.value
    db.flush()
    return row


def resolve_suggestions(db: Session, plan: IepPlan) -> None:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(IepPlanSuggestion).where(
            IepPlanSuggestion.iep_plan_id == plan.id,
            IepPlanSuggestion.resolved_at.is_(None),
        )
    ).all()
    for row in rows:
        row.resolved_at = now
    if plan.status == IepPlanStatus.EDITS_SUGGESTED.value:
        plan.status = IepPlanStatus.DRAFT.value
    db.flush()


def parent_acknowledge_plan(db: Session, plan: IepPlan, parent_user: User) -> IepPlan:
    sections = _parse_sections(plan.sections_json)
    sections.verification.client_name = parent_user.full_name or ""
    sections.verification.client_date = date.today().isoformat()
    plan.sections_json = _dump_sections(sections)
    plan.status = IepPlanStatus.PARENT_ACKNOWLEDGED.value
    db.flush()
    return plan


def approve_plan(db: Session, plan: IepPlan) -> IepPlan:
    plan.status = IepPlanStatus.APPROVED.value
    if not plan.published_at:
        plan.published_at = datetime.now(timezone.utc)
    db.flush()
    purge_superseded_iep_plans(db, plan.case_id)
    return plan


def purge_superseded_iep_plans(db: Session, case_id: int, *, retention_days: int = 30) -> int:
    """Delete older plan rows for a case once the latest is approved/acknowledged."""
    latest = get_latest_plan(db, case_id)
    if not latest or latest.status not in {
        IepPlanStatus.APPROVED.value,
        IepPlanStatus.PARENT_ACKNOWLEDGED.value,
    }:
        return 0
    anchor = _aware(latest.published_at) or _aware(latest.updated_at) or _aware(latest.created_at)
    if not anchor:
        return 0
    cutoff = anchor - timedelta(days=retention_days)
    removed = 0
    rows = db.scalars(select(IepPlan).where(IepPlan.case_id == case_id, IepPlan.id != latest.id)).all()
    for row in rows:
        row_updated = _aware(row.updated_at) or _aware(row.created_at)
        if row_updated and row_updated < cutoff:
            db.delete(row)
            removed += 1
    if removed:
        db.flush()
    return removed


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def _supplementary_attachments_html(db: Session, sections: IepPlanSections) -> str:
    ids = sections.supplementary_attachment_ids or []
    if not ids:
        return ""
    names = []
    for aid in ids:
        att = db.get(Attachment, aid)
        if att:
            names.append(att.file_name or f"Attachment #{aid}")
    if not names:
        return ""
    items = "".join(f"<li>{_esc(n)}</li>" for n in names)
    return f"<h2>Supplementary documents</h2><ul>{items}</ul>"


def _sections_to_html(sections: IepPlanSections, db: Session | None = None) -> str:
    parts = [IEP_DOC_TABLE_STYLE]
    h = sections.header
    if h.child_name or h.about_child_brief:
        parts.append("<h2>About the child</h2>")
        meta = "<br/>".join(
            _esc(x)
            for x in [
                f"Child: {h.child_name}" if h.child_name else "",
                f"Age: {h.age_label}" if h.age_label else "",
                f"Diagnosis: {h.diagnosis}" if h.diagnosis else "",
                f"Service: {h.service_provided}" if h.service_provided else "",
                f"Parents: {h.parents_names}" if h.parents_names else "",
                f"Therapist: {h.therapist_name}" if h.therapist_name else "",
                f"School/Home: {h.school_or_home_name}" if h.school_or_home_name else "",
                f"Class: {h.class_grade}" if h.class_grade else "",
                f"Evaluation date: {h.date_of_evaluation}" if h.date_of_evaluation else "",
                f"IEP meeting date: {h.date_of_iep_meeting}" if h.date_of_iep_meeting else "",
                f"Review date: {h.review_date}" if h.review_date else "",
            ]
            if x
        )
        if meta:
            parts.append(f"<p>{meta}</p>")
        if h.about_child_brief.strip():
            parts.append(f"<p>{_esc(h.about_child_brief)}</p>")
    elif sections.about_child.strip():
        parts.append(f"<h2>About the child</h2><p>{_esc(sections.about_child)}</p>")
    if sections.observations.strip():
        parts.append(f"<h2>Observations</h2><p>{_esc(sections.observations)}</p>")
    if sections.learning_environments:
        rows = "".join(
            f"<tr><td>{_esc(r.environment)}</td><td>{_esc(r.strengths)}</td>"
            f"<td>{_esc(r.goals)}</td><td>{_esc(r.strategies)}</td>"
            f"<td>{_esc(r.supports_needed)}</td></tr>"
            for r in sections.learning_environments
            if r.environment or r.strengths or r.goals or r.strategies or r.supports_needed
        )
        if rows:
            parts.append(
                '<div class="iep-doc-section"><h2>Learning environments</h2>'
                '<table class="iep-doc-table">'
                "<thead><tr><th>Environment</th><th>Strengths</th><th>Goals</th>"
                "<th>Strategies</th><th>Supports needed</th></tr></thead><tbody>"
                f"{rows}</tbody></table></div>"
            )
    if sections.challenges.strip():
        parts.append(f"<h2>Challenges</h2><p>{_esc(sections.challenges)}</p>")
    elif sections.referral.strip():
        parts.append(f"<h2>Challenges</h2><p>{_esc(sections.referral)}</p>")
    for perf in sections.current_performance:
        if perf.notes.strip():
            parts.append(f"<h3>Current performance — {perf.domain}</h3><p>{_esc(perf.notes)}</p>")
    ls = sections.learning_style
    if ls.styles or ls.elaboration.strip():
        parts.append(
            f"<h2>Learning style</h2><p>{_esc(', '.join(ls.styles))}</p><p>{_esc(ls.elaboration)}</p>"
        )
    if sections.interventions.strip():
        parts.append(f"<h2>Interventions</h2><p>{_esc(sections.interventions)}</p>")
    td = sections.talent_development
    if td.strengths or td.goals or td.strategies:
        parts.append(
            f"<h2>Talent development</h2><p><b>Strengths:</b> {_esc(td.strengths)}</p>"
            f"<p><b>Goals:</b> {_esc(td.goals)}</p><p><b>Strategies:</b> {_esc(td.strategies)}</p>"
        )
    other = sections.other_areas_of_need
    if other.areas_of_need or other.goals or other.strategies:
        parts.append(
            f"<h2>Other areas of need</h2><p><b>Areas:</b> {_esc(other.areas_of_need)}</p>"
            f"<p><b>Goals:</b> {_esc(other.goals)}</p><p><b>Strategies:</b> {_esc(other.strategies)}</p>"
        )
    if sections.intervention_by_insighte.strip():
        parts.append(f"<h2>Intervention by Insighte</h2><p>{_esc(sections.intervention_by_insighte)}</p>")
    v = sections.verification
    verifier = (v.prepared_by_name or "").strip() or (
        f"{v.therapist_name} (therapist)" if v.therapist_verified else ""
    )
    parts.append(
        '<div class="iep-doc-section"><h2>Verification</h2>'
        f"<p><strong>Verified by:</strong> {_esc(verifier)} "
        f"({_esc(v.prepared_at or v.therapist_date)})"
        f"{f' · {_esc(v.prepared_by_role)}' if v.prepared_by_role else ''}</p>"
        f"<p><strong>Assigned therapist:</strong> {_esc(v.therapist_name)} "
        f"License: {_esc(v.therapist_license_no)}</p>"
        f"<p><strong>Case manager:</strong> {_esc(v.case_manager_name)} "
        f"({_esc(v.case_manager_date)})</p>"
        f"<p><strong>Parent acknowledgement:</strong> {_esc(v.client_name or 'Pending')} "
        f"({_esc(v.client_date)})</p></div>"
    )
    if db:
        supp = _supplementary_attachments_html(db, sections)
        if supp:
            parts.append(supp)
    return "".join(parts) or "<p>IEP plan</p>"


def sections_to_preview_html(db: Session, plan: IepPlan) -> str:
    sections = _parse_sections(plan.sections_json)
    return _sections_to_html(sections, db)


def sections_to_pdf_bytes(db: Session, plan: IepPlan) -> bytes:
    from app.services.report_pdf_service import build_report_pdf_bytes

    sections = _parse_sections(plan.sections_json)
    case = case_service.get_case(db, plan.case_id)
    child_name = case.child.full_name if case and case.child else ""
    case_code = case.case_code if case else ""
    html = _sections_to_html(sections, db)
    return build_report_pdf_bytes(
        title=f"IEP {plan.version}",
        child_name=child_name,
        case_code=case_code,
        category="IEP",
        month_label=sections.header.date_of_iep_meeting or "",
        body_html=html,
        plan_next_month=None,
    )


def share_plan_with_parent(db: Session, plan: IepPlan, user: User) -> IepPlan:
    case = case_service.get_case(db, plan.case_id)
    if not case:
        raise ValueError("Case not found")
    sections = _parse_sections(plan.sections_json)
    _sync_verification(sections, user, case, db)
    errors = validate_sections_for_share(sections)
    if errors:
        raise ValueError("; ".join(errors))
    plan.sections_json = _dump_sections(sections)
    html = _sections_to_html(sections, db)
    att = None
    if plan.attachment_id:
        att = db.get(Attachment, plan.attachment_id)
    if not att:
        from app.storage.object_io import put_stored_bytes

        export_name = f"IEP_{case.case_code}_{plan.version}.html"
        file_path, _provider = put_stored_bytes(
            "iep-exports",
            f"case_{case.id}",
            f"plan_{plan.id}",
            filename=export_name,
            data=html.encode("utf-8"),
            content_type="text/html; charset=utf-8",
        )
        att = Attachment(
            case_id=case.id,
            entity_type="iep",
            entity_id=plan.id,
            file_name=export_name,
            file_path=file_path,
            version=plan.version,
            visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
            uploaded_by_user_id=user.id,
        )
        db.add(att)
        db.flush()
        plan.attachment_id = att.id
    else:
        from app.storage.object_io import is_object_store_key, put_stored_bytes

        att.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
        export_name = att.file_name or f"IEP_{case.case_code}_{plan.version}.html"
        if is_object_store_key(att.file_path):
            file_path, _provider = put_stored_bytes(
                "iep-exports",
                f"case_{case.id}",
                f"plan_{plan.id}",
                filename=export_name,
                data=html.encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )
            att.file_path = file_path
        else:
            legacy = Path(att.file_path)
            if legacy.parent:
                legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text(html, encoding="utf-8")
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


def list_plans_scoped(db: Session, user, *, status=None, limit: int = 50) -> list[dict]:
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
