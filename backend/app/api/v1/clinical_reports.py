from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.module_access import is_view_only_user
from app.core.permissions import RoleName, user_has_permission
from app.models.user import User
from app.services import (
    case_service,
    goal_strategy_matching_service,
    iep_report_service,
    observation_report_service,
    report_engine_service,
    report_evidence_service,
    report_status_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["clinical-reports"])


def _case_for_user(db: Session, user: User, case_id: int):
    if RoleName.PARENT.value in (user.role_names or []):
        from app.api.v1.parent import _parent_case_or_404

        return _parent_case_or_404(db, user, case_id)
    from app.api.v1.cases import _case_for_user as cases_case_for_user

    return cases_case_for_user(db, user, case_id)


_CLINICAL_REPORT_WRITE_ROLES = frozenset(
    {
        RoleName.SUPER_ADMIN.value,
        RoleName.MODULE_ADMIN.value,
        RoleName.ADMIN.value,
        RoleName.CASE_MANAGER.value,
        RoleName.SUPERVISOR.value,
        RoleName.THERAPIST.value,
    }
)

_CLINICAL_REPORT_SHARE_ROLES = frozenset(
    {
        RoleName.SUPER_ADMIN.value,
        RoleName.MODULE_ADMIN.value,
        RoleName.ADMIN.value,
        RoleName.CASE_MANAGER.value,
        RoleName.SUPERVISOR.value,
    }
)


def _case_for_user_write(db: Session, user: User, case_id: int):
    """Assigned-case write for clinical reports — not staff programme-module grants.

    Therapists and case managers start/edit IEP and observation reports on cases
    they can already see. Programme-module write (homecare/shadow_support) is the
    admin case-edit gate and would 403 therapists; it also auto-completes overdue
    therapist handovers, which must not block report start.
    """
    case = _case_for_user(db, user, case_id)
    if is_view_only_user(user):
        raise HTTPException(status_code=403, detail="View-only access — changes are not allowed")
    if not _CLINICAL_REPORT_WRITE_ROLES.intersection(user.role_names or []):
        raise HTTPException(
            status_code=403,
            detail="You can view this case but cannot edit clinical reports.",
        )
    return case


def _case_for_user_share(db: Session, user: User, case_id: int):
    case = _case_for_user(db, user, case_id)
    if is_view_only_user(user):
        raise HTTPException(status_code=403, detail="View-only access — changes are not allowed")
    if not _CLINICAL_REPORT_SHARE_ROLES.intersection(user.role_names or []):
        raise HTTPException(
            status_code=403,
            detail="Only the case manager can share this plan with the family.",
        )
    return case


def _report_or_404(db: Session, report_id: int):
    report = report_engine_service.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


class SectionPatch(BaseModel):
    narrative_text: Optional[str] = None
    internal_notes: Optional[str] = None
    structured_data: Optional[dict[str, Any]] = None


class GoalCandidateCreate(BaseModel):
    label: str = Field(min_length=3)
    domain_key: str = "general"
    baseline_note: str = ""
    desired_direction: str = ""
    source_section_key: str = "emerging_goals"


class StrategyCandidateCreate(BaseModel):
    label: str = Field(min_length=3)
    description: str = ""
    domain_key: Optional[str] = None


class ReturnBody(BaseModel):
    comment: str = Field(min_length=3)


class ApproveBody(BaseModel):
    share_with_parent: bool = False
    comment: Optional[str] = None


class EvidenceAttachBody(BaseModel):
    case_document_id: int
    section_key: Optional[str] = None
    evidence_label: Optional[str] = None


class IepGoalCreate(BaseModel):
    goal_source_id: Optional[int] = None
    source_type: str = "manual"
    title: str = ""
    goal_statement: str = ""
    domain: str = "general"
    baseline_current_state: str = ""
    desired_state: str = ""
    participation: str = "not_yet_participating"
    independence_support_needed: str = "full_adult_support"
    goal_achievement: str = "baseline"
    environments: list[str] = Field(default_factory=list)
    parent_facing_wording: str = ""


class IepGoalPatch(BaseModel):
    title: Optional[str] = None
    goal_statement: Optional[str] = None
    domain: Optional[str] = None
    baseline_current_state: Optional[str] = None
    desired_state: Optional[str] = None
    participation: Optional[str] = None
    independence_support_needed: Optional[str] = None
    goal_achievement: Optional[str] = None
    environments: Optional[list[str]] = None
    parent_facing_wording: Optional[str] = None
    custom_strategy_notes: Optional[str] = None
    therapist_notes: Optional[str] = None
    cm_notes: Optional[str] = None


class IepStrategyLink(BaseModel):
    strategy_id: int
    strategy_source_type: str = "repository"


class IepStrategyCandidateCreate(BaseModel):
    label: str = Field(min_length=3)
    when_to_use: str = ""
    how_to_use: str = ""
    domain_key: Optional[str] = None
    environment_context: Optional[str] = None
    strategy_steps: list[str] = Field(default_factory=list)


class IepApproveChangesBody(BaseModel):
    change_ids: list[str] = Field(min_length=1)


class IepReturnChangesBody(BaseModel):
    change_ids: list[str] = Field(min_length=1)
    comment: str = Field(min_length=3)


class ParentIepInputBody(BaseModel):
    text: str = Field(min_length=3)


@router.get("/cases/{case_id}/reports")
def list_reports(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _case_for_user(db, user, case_id)
    rows = report_engine_service.list_case_reports(db, case.id)
    return {
        "items": [
            {
                "id": r.id,
                "report_type": r.report_type,
                "title": r.title,
                "status": r.status,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ]
    }


@router.get("/cases/{case_id}/reports/dashboard")
def reports_dashboard(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _case_for_user(db, user, case_id)
    return report_engine_service.case_dashboard(db, case.id)


@router.get("/cases/{case_id}/reports/observation/summary")
def observation_summary(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _case_for_user(db, user, case_id)
    try:
        return report_engine_service.observation_summary(db, case, user)
    except Exception as exc:
        logger.exception("observation_summary failed case_id=%s", case_id)
        raise HTTPException(status_code=503, detail="Could not load observation summary") from exc


@router.post("/cases/{case_id}/reports/observation/start")
def start_observation(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        case = _case_for_user_write(db, user, case_id)
        report = observation_report_service.start_observation(db, case, user)
        db.commit()
        return report_engine_service.serialize_report_workspace(db, report, case)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as exc:
        logger.exception("start_observation failed case_id=%s", case_id)
        raise HTTPException(status_code=503, detail="Could not start observation report") from exc


@router.get("/cases/{case_id}/reports/{report_type}")
def get_report_by_type(
    case_id: int,
    report_type: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user(db, user, case_id)
    parent = report_engine_service.user_is_parent(user)
    if report_type == "observation":
        try:
            if parent:
                report = report_engine_service.get_active_observation_report(db, case.id)
                if not report_engine_service.parent_may_view_report(report):
                    raise HTTPException(status_code=404, detail="No observation report is available yet")
                return report_engine_service.serialize_parent_safe_observation(db, report, case)
            report, _ = observation_report_service.ensure_checklist_bridge(db, case, user)
            db.commit()
            return report_engine_service.serialize_report_workspace(db, report, case)
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as exc:
            logger.exception("get_report_by_type observation failed case_id=%s", case_id)
            raise HTTPException(status_code=503, detail="Could not load observation report") from exc
    if report_type == "iep":
        report = report_engine_service.get_active_iep_report(db, case.id)
        if not report:
            raise HTTPException(status_code=404, detail="No active IEP report")
        if parent:
            if not report_engine_service.parent_may_view_report(report):
                raise HTTPException(status_code=404, detail="No IEP plan is available yet")
            return report_engine_service.serialize_parent_safe_iep(db, report, case)
        return report_engine_service.serialize_report_workspace(db, report, case)
    raise HTTPException(status_code=404, detail="Report type not implemented yet")


@router.get("/reports/{report_id}")
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    case = _case_for_user(db, user, report.case_id)
    if report_engine_service.user_is_parent(user):
        if not report_engine_service.parent_may_view_report(report):
            raise HTTPException(status_code=404, detail="Report not found")
        if report.report_type == "iep":
            return report_engine_service.serialize_parent_safe_iep(db, report, case)
        return report_engine_service.serialize_parent_safe_observation(db, report, case)
    return report_engine_service.serialize_report_workspace(db, report, case)


@router.get("/reports/{report_id}/sections")
def list_sections(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    ws = report_engine_service.serialize_report_workspace(db, report, case_service.get_case(db, report.case_id))
    return {"sections": ws["sections"]}


@router.patch("/reports/{report_id}/sections/{section_key}")
def patch_section(
    report_id: int,
    section_key: str,
    payload: SectionPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    if not report_status_service.can_therapist_edit(report, user):
        raise HTTPException(status_code=403, detail="Cannot edit this report")
    try:
        sec = report_engine_service.patch_section(
            db,
            report,
            section_key,
            narrative_text=payload.narrative_text,
            internal_notes=payload.internal_notes,
            structured_data=payload.structured_data,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return report_engine_service.serialize_section(sec, report_type=report.report_type)


@router.post("/reports/{report_id}/submit")
def submit_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    case = _case_for_user_write(db, user, report.case_id)
    try:
        if report.report_type == "observation":
            observation_report_service.submit_observation(db, case, user)
        elif report.report_type == "iep":
            report_status_service.submit_report(db, report, user, readiness_ok=True)
        else:
            from app.models.clinical_report import ClinicalReportSection
            from sqlalchemy import select

            sections = list(db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all())
            ready = report_engine_service.required_sections_complete(sections)
            report_status_service.submit_report(db, report, user, readiness_ok=ready)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return report_engine_service.serialize_report_workspace(db, report, case)


@router.post("/reports/{report_id}/save-draft")
def save_draft_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    report = _report_or_404(db, report_id)
    case = _case_for_user_write(db, user, report.case_id)
    if not report_status_service.can_therapist_edit(report, user):
        raise HTTPException(status_code=403, detail="Cannot edit this report")
    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)
    return report_engine_service.serialize_report_workspace(db, report, case)


@router.post("/reports/{report_id}/approve")
def approve_report(report_id: int, payload: ApproveBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    if not (
        user_has_permission(user, "monthly_report.approve")
        or user_has_permission(user, "admin.override")
    ):
        raise HTTPException(
            status_code=403,
            detail="Case access alone does not grant approval. A reviewer role is required.",
        )
    try:
        report_status_service.approve_report(db, report, user, share_parent=payload.share_with_parent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    case = case_service.get_case(db, report.case_id)
    return report_engine_service.serialize_report_workspace(db, report, case)


@router.post("/reports/{report_id}/share-with-parent")
def share_report_with_parent(
    report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    _case_for_user_share(db, user, report.case_id)
    try:
        report_status_service.share_report_with_parent(db, report, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    case = case_service.get_case(db, report.case_id)
    return report_engine_service.serialize_report_workspace(db, report, case)


@router.post("/reports/{report_id}/return")
def return_report(report_id: int, payload: ReturnBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    try:
        report_status_service.return_report(db, report, user, payload.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    case = case_service.get_case(db, report.case_id)
    return report_engine_service.serialize_report_workspace(db, report, case)


@router.get("/reports/{report_id}/evidence-summary")
def evidence_summary(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    return report_evidence_service.evidence_summary(db, report)


@router.post("/reports/{report_id}/evidence")
def attach_report_evidence(
    report_id: int,
    payload: EvidenceAttachBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    if not report_status_service.can_therapist_edit(report, user):
        raise HTTPException(status_code=403, detail="Cannot edit this report")
    try:
        row = report_evidence_service.attach_case_document(
            db,
            report,
            case_document_id=payload.case_document_id,
            section_key=payload.section_key,
            evidence_label=payload.evidence_label,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return {
        "id": row.id,
        "evidence_label": row.evidence_label,
        "source_type": row.source_type,
        "source_id": row.source_id,
    }


@router.post("/reports/{report_id}/observation/apply-insights")
def apply_observation_insights(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    if not report_status_service.can_therapist_edit(report, user):
        raise HTTPException(status_code=403, detail="Cannot edit this report")
    try:
        result = observation_report_service.apply_session_insights(db, report, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    case = case_service.get_case(db, report.case_id)
    ws = report_engine_service.serialize_report_workspace(db, report, case)
    return {"applied": result, "workspace": ws}


@router.post("/reports/{report_id}/observation/goal-candidates")
def create_goal_candidate(
    report_id: int,
    payload: GoalCandidateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    row = observation_report_service.create_goal_candidate(
        db,
        report,
        user,
        label=payload.label,
        domain_key=payload.domain_key,
        baseline_note=payload.baseline_note,
        desired_direction=payload.desired_direction,
        source_section_key=payload.source_section_key,
    )
    db.commit()
    return {"id": row.id, "label": row.label, "status": row.status}


@router.post("/reports/{report_id}/observation/strategy-candidates")
def create_strategy_candidate(
    report_id: int,
    payload: StrategyCandidateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    row = observation_report_service.create_strategy_candidate(
        db, report, user, label=payload.label, description=payload.description, domain_key=payload.domain_key
    )
    db.commit()
    return {"id": row.id, "label": row.label, "status": row.status}


@router.get("/reports/{report_id}/observation/candidates")
def list_candidates(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    return observation_report_service.list_candidates(db, report.id)


@router.get("/reports/{report_id}/preview")
def preview_report(
    report_id: int,
    mode: str = "clinical",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    case = _case_for_user(db, user, report.case_id)
    if report_engine_service.user_is_parent(user):
        if not report_engine_service.parent_may_view_report(report):
            raise HTTPException(status_code=404, detail="Report not found")
        if report.report_type == "iep":
            return report_engine_service.serialize_parent_safe_iep(db, report, case)
        return report_engine_service.serialize_parent_safe_observation(db, report, case)
    if report.report_type == "iep":
        if mode == "parent":
            return report_engine_service.serialize_parent_safe_iep(db, report, case)
        return report_engine_service.serialize_report_workspace(db, report, case)
    return report_engine_service.serialize_parent_safe_observation(db, report, case)


@router.post("/reports/{report_id}/observation/generate-insights")
def generate_observation_insights(
    report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    case = _case_for_user(db, user, report.case_id)
    try:
        payload = observation_report_service.generate_session_insights(db, report, case)
        db.commit()
        return payload
    except Exception as exc:
        logger.exception("generate_insights failed report_id=%s", report_id)
        raise HTTPException(status_code=503, detail="Could not generate session insights") from exc


@router.get("/reports/{report_id}/observation/strategy-matches")
def strategy_matches(
    report_id: int,
    q: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    return {"items": goal_strategy_matching_service.find_matching_strategies(db, q, case_id=report.case_id)}


@router.post("/reports/{report_id}/generate-iep-draft")
def generate_iep_draft(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    if report.report_type != "iep":
        raise HTTPException(status_code=400, detail="Use IEP report generate-draft endpoint")
    result = iep_report_service.generate_iep_draft_from_observation(db, report, user)
    db.commit()
    case = case_service.get_case(db, report.case_id)
    return {"draft": result, "workspace": report_engine_service.serialize_report_workspace(db, report, case)}


# --- IEP report routes ---


@router.get("/cases/{case_id}/reports/iep/summary")
def iep_summary(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _case_for_user(db, user, case_id)
    try:
        return report_engine_service.iep_summary(db, case, user)
    except Exception as exc:
        logger.exception("iep_summary failed case_id=%s", case_id)
        raise HTTPException(status_code=503, detail="Could not load IEP summary") from exc


@router.post("/cases/{case_id}/reports/iep/start")
def start_iep(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        case = _case_for_user_write(db, user, case_id)
        report = iep_report_service.start_iep(db, case, user)
        db.commit()
        return report_engine_service.serialize_report_workspace(db, report, case)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as exc:
        logger.exception("start_iep failed case_id=%s", case_id)
        raise HTTPException(status_code=503, detail="Could not start IEP") from exc


@router.get("/cases/{case_id}/reports/iep/available-goals")
def iep_available_goals(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _case_for_user(db, user, case_id)
    return iep_report_service.list_available_goals_for_iep(db, case_id)


@router.get("/cases/{case_id}/reports/iep/available-strategies")
def iep_available_strategies(
    case_id: int,
    goal_id: Optional[str] = None,
    domain: Optional[str] = None,
    environment: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    return iep_report_service.list_available_strategies_for_iep(
        db, case_id, goal_id=goal_id, domain=domain, environment=environment
    )


@router.post("/reports/{report_id}/iep/generate-draft")
def iep_generate_draft(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    result = iep_report_service.generate_iep_draft_from_observation(db, report, user)
    db.commit()
    case = case_service.get_case(db, report.case_id)
    return {"draft": result, "workspace": report_engine_service.serialize_report_workspace(db, report, case)}


@router.post("/reports/{report_id}/iep/goals")
def iep_add_goal(report_id: int, payload: IepGoalCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    if payload.goal_source_id:
        goal = iep_report_service.add_goal_to_iep(
            db, report, user, goal_source_id=payload.goal_source_id, source_type=payload.source_type
        )
    else:
        goal = iep_report_service.create_manual_goal_in_iep(db, report, user, payload.model_dump())
    db.commit()
    return goal


@router.patch("/reports/{report_id}/iep/goals/{iep_goal_id}")
def iep_patch_goal(
    report_id: int, iep_goal_id: str, payload: IepGoalPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    goal = iep_report_service.patch_iep_goal(db, report, user, iep_goal_id, payload.model_dump(exclude_none=True))
    db.commit()
    return goal


@router.delete("/reports/{report_id}/iep/goals/{iep_goal_id}")
def iep_delete_goal(report_id: int, iep_goal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    iep_report_service.delete_iep_goal(db, report, user, iep_goal_id)
    db.commit()
    return {"ok": True}


@router.post("/reports/{report_id}/iep/goals/{iep_goal_id}/strategies")
def iep_link_strategy(
    report_id: int, iep_goal_id: str, payload: IepStrategyLink, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    goal = iep_report_service.link_strategy_to_iep_goal(
        db, report, user, iep_goal_id, payload.strategy_id, payload.strategy_source_type
    )
    db.commit()
    return goal


@router.delete("/reports/{report_id}/iep/goals/{iep_goal_id}/strategies/{strategy_id}")
def iep_unlink_strategy(
    report_id: int, iep_goal_id: str, strategy_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    goal = iep_report_service.unlink_strategy_from_iep_goal(db, report, user, iep_goal_id, strategy_id)
    db.commit()
    return goal


@router.post("/reports/{report_id}/iep/goals/{iep_goal_id}/strategy-candidates")
def iep_create_strategy_candidate(
    report_id: int,
    iep_goal_id: str,
    payload: IepStrategyCandidateCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    row = iep_report_service.create_strategy_candidate_from_iep(db, report, user, iep_goal_id, payload.model_dump())
    db.commit()
    return row


@router.post("/reports/{report_id}/iep/sync-active-plan")
def iep_sync_active_plan(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    result = iep_report_service.sync_approved_iep_goals_to_active_case_plan(db, report, user)
    db.commit()
    return result


@router.get("/reports/{report_id}/iep/preview")
def iep_preview(
    report_id: int, mode: str = "clinical", user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    case = _case_for_user(db, user, report.case_id)
    if report_engine_service.user_is_parent(user):
        if not report_engine_service.parent_may_view_report(report):
            raise HTTPException(status_code=404, detail="Report not found")
        return report_engine_service.serialize_parent_safe_iep(db, report, case)
    if mode == "parent":
        return report_engine_service.serialize_parent_safe_iep(db, report, case)
    return report_engine_service.serialize_report_workspace(db, report, case)


@router.get("/reports/{report_id}/iep/pdf")
def iep_pdf(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi.responses import Response

    report = _report_or_404(db, report_id)
    case = _case_for_user(db, user, report.case_id)
    parent = report_engine_service.user_is_parent(user)
    if parent and not report_engine_service.parent_may_view_report(report):
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        data, filename = report_engine_service.iep_pdf_bytes(db, report, case, parent_safe=parent)
    except Exception as exc:
        logger.exception("iep_pdf failed report_id=%s", report_id)
        raise HTTPException(status_code=503, detail="Could not download this IEP") from exc
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/{report_id}/iep/pending-changes")
def iep_pending_changes(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    return {"items": iep_report_service.list_pending_changes(db, report)}


@router.post("/reports/{report_id}/iep/approve-changes")
def iep_approve_changes(
    report_id: int, payload: IepApproveChangesBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    result = iep_report_service.approve_changes(db, report, user, payload.change_ids)
    db.commit()
    return result


@router.post("/reports/{report_id}/iep/return-changes")
def iep_return_changes(
    report_id: int, payload: IepReturnChangesBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    result = iep_report_service.return_changes(db, report, user, payload.change_ids, payload.comment)
    db.commit()
    return result


@router.post("/reports/{report_id}/iep/goals/{iep_goal_id}/mark-achieved")
def iep_mark_achieved(
    report_id: int, iep_goal_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    goal = iep_report_service.mark_goal_achieved(db, report, user, iep_goal_id)
    db.commit()
    return goal


@router.post("/reports/{report_id}/iep/amend")
def iep_amend(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    iep_report_service.record_amendment(db, report, user)
    db.commit()
    case = case_service.get_case(db, report.case_id)
    return report_engine_service.serialize_report_workspace(db, report, case)


@router.get("/cases/{case_id}/clinical/repository-search")
def clinical_repository_search(
    case_id: int,
    q: str = "",
    kind: str = "goals",
    domain: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _case_for_user(db, user, case_id)
    return iep_report_service.search_clinical_repository(db, case_id, q=q, kind=kind, domain=domain)


@router.post("/reports/{report_id}/clinical/generate-goal-strategy-drafts")
def clinical_generate_goal_strategy_drafts(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    case = _case_for_user(db, user, report.case_id)
    return iep_report_service.generate_goal_strategy_drafts(db, report, case)


@router.post("/reports/{report_id}/iep/generate-suggestions")
def iep_generate_suggestions(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.core.config import settings

    if not getattr(settings, "iep_review_suggestions_enabled", False):
        raise HTTPException(status_code=403, detail="IEP review suggestions are not enabled in this environment.")
    report = _report_or_404(db, report_id)
    case = _case_for_user(db, user, report.case_id)
    return iep_report_service.generate_iep_suggestions(db, report, case)


class IepStakeholderAction(BaseModel):
    comment: str = ""


@router.post("/reports/{report_id}/iep/send-for-stakeholder-approval")
def iep_send_stakeholder_approval(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services import iep_approval_service

    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    result = iep_approval_service.send_for_stakeholder_approval(db, report, user)
    db.commit()
    case = case_service.get_case(db, report.case_id)
    return {"approval": result, "workspace": report_engine_service.serialize_report_workspace(db, report, case)}


@router.post("/reports/{report_id}/iep/stakeholder-approve")
def iep_stakeholder_approve(
    report_id: int,
    role: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import iep_approval_service

    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    try:
        result = iep_approval_service.stakeholder_approve(db, report, user, role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return {"approval": result}


@router.post("/reports/{report_id}/iep/stakeholder-request-review")
def iep_stakeholder_request_review(
    report_id: int,
    role: str,
    payload: IepStakeholderAction,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import iep_approval_service

    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    try:
        result = iep_approval_service.stakeholder_request_review(db, report, user, role, payload.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return {"approval": result}


@router.post("/reports/{report_id}/iep/resend-for-approval")
def iep_resend_for_approval(
    report_id: int,
    payload: IepStakeholderAction,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import iep_approval_service

    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    try:
        result = iep_approval_service.cm_resend_for_approval(db, report, user, payload.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    case = case_service.get_case(db, report.case_id)
    return {"approval": result, "workspace": report_engine_service.serialize_report_workspace(db, report, case)}


@router.get("/reports/{report_id}/iep/review-thread")
def iep_review_thread(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services import iep_approval_service

    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    return {"items": iep_approval_service.list_review_thread(db, report_id)}


@router.get("/cases/{case_id}/reports/iep/versions")
def iep_versions(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _case_for_user(db, user, case_id)
    from app.services.iep_reminder_service import list_iep_versions_for_case

    return {"items": list_iep_versions_for_case(db, case_id)}


@router.post("/cases/{case_id}/reports/iep/renew")
def iep_renew_prompt(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.iep_reminder_service import prompt_renew_iep

    case = _case_for_user_write(db, case_id)
    roles = {r.name for r in getattr(user, "roles", []) or []}
    if not (roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER", "SUPERVISOR"}):
        raise HTTPException(status_code=403, detail="Case manager access required")
    try:
        result = prompt_renew_iep(db, case, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    return result
