"""CANONICAL: clinical_reports engine API — observation, IEP, monthly, progress.

Future single report lifecycle spine. Legacy /api/v1/reports/* routes delegate
here over time. See docs/REPORT_ARCHITECTURE.md.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
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
    from app.api.v1.cases import _case_for_user as cases_case_for_user

    return cases_case_for_user(db, user, case_id)


def _case_for_user_write(db: Session, user: User, case_id: int):
    from app.api.v1.cases import _case_for_user_write as cases_write

    return cases_write(db, user, case_id)


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
    case = _case_for_user_write(db, user, case_id)
    try:
        report = observation_report_service.start_observation(db, case, user)
        db.commit()
        return report_engine_service.serialize_report_workspace(db, report, case)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as exc:
        logger.exception("start_observation failed case_id=%s", case_id)
        raise HTTPException(status_code=503, detail="Could not start observation report") from exc


@router.get("/cases/{case_id}/reports/monthly/summary")
def monthly_summary(
    case_id: int,
    month: str = Query(..., min_length=4),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user(db, user, case_id)
    try:
        return report_engine_service.monthly_summary(db, case, user, month)
    except Exception as exc:
        logger.exception("monthly_summary failed case_id=%s", case_id)
        raise HTTPException(status_code=503, detail="Could not load monthly summary") from exc


@router.post("/cases/{case_id}/reports/monthly/start")
def start_monthly(
    case_id: int,
    month: str = Query(..., min_length=4),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user_write(db, user, case_id)
    try:
        report = report_engine_service.get_or_create_monthly_report(db, case, user, month)
        db.commit()
        return report_engine_service.serialize_report_workspace(db, report, case)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as exc:
        logger.exception("start_monthly failed case_id=%s", case_id)
        raise HTTPException(status_code=503, detail="Could not start monthly report") from exc


@router.post("/reports/{report_id}/monthly/compile-evidence")
def compile_monthly_evidence(
    report_id: int,
    force: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import monthly_evidence_compiler_service as compiler_svc
    from app.services.report_engine_service import _report_month_from_metadata

    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    if report.report_type != "monthly":
        raise HTTPException(status_code=400, detail="Not a monthly report")
    month = _report_month_from_metadata(report)
    if not month:
        raise HTTPException(status_code=400, detail="Report month not set")
    payload = compiler_svc.compile_monthly_evidence_snapshot(
        db,
        case_id=report.case_id,
        month=month,
        clinical_report_id=report.id,
        user_id=user.id,
        force=force,
    )
    return payload


@router.get("/reports/{report_id}/evidence-snapshot")
def get_monthly_evidence_snapshot(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import monthly_evidence_compiler_service as compiler_svc
    from app.services.report_engine_service import _report_month_from_metadata

    report = _report_or_404(db, report_id)
    _case_for_user_write(db, user, report.case_id)
    month = _report_month_from_metadata(report)
    if not month:
        raise HTTPException(status_code=400, detail="Report month not set")
    snap = compiler_svc.get_latest_snapshot(db, report.case_id, month)
    if not snap:
        raise HTTPException(status_code=404, detail="No compiled evidence snapshot yet")
    return snap


@router.post("/reports/{report_id}/monthly/populate-from-evidence")
def populate_monthly_from_evidence(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _report_or_404(db, report_id)
    case = _case_for_user_write(db, user, report.case_id)
    if report.report_type != "monthly":
        raise HTTPException(status_code=400, detail="Not a monthly report")
    if not report_status_service.can_therapist_edit(report, user):
        raise HTTPException(status_code=403, detail="Cannot edit this report")
    try:
        result = report_engine_service.populate_monthly_from_evidence(db, report)
        db.commit()
        result["workspace"] = report_engine_service.serialize_report_workspace(db, report, case)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/cases/{case_id}/reports/{report_type}")
def get_report_by_type(
    case_id: int,
    report_type: str,
    month: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = _case_for_user(db, user, case_id)
    if report_type == "observation":
        try:
            report, _ = observation_report_service.ensure_checklist_bridge(db, case, user)
            db.commit()
            return report_engine_service.serialize_report_workspace(db, report, case)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as exc:
            logger.exception("get_report_by_type observation failed case_id=%s", case_id)
            raise HTTPException(status_code=503, detail="Could not load observation report") from exc
    if report_type == "iep":
        report = report_engine_service.get_active_iep_report(db, case.id)
        if not report:
            raise HTTPException(status_code=404, detail="No active IEP report")
        return report_engine_service.serialize_report_workspace(db, report, case)
    if report_type == "monthly":
        if not month:
            raise HTTPException(status_code=400, detail="month query parameter required")
        report = report_engine_service.get_monthly_report_for_case_month(db, case.id, month)
        if not report:
            raise HTTPException(status_code=404, detail="No monthly report for this month")
        return report_engine_service.serialize_report_workspace(db, report, case)
    raise HTTPException(status_code=404, detail="Report type not implemented yet")


@router.get("/reports/{report_id}")
def get_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report_or_404(db, report_id)
    case = _case_for_user(db, user, report.case_id)
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
            validation = iep_report_service.validate_iep_submit(db, report)
            if not validation.get("ready"):
                raise ValueError("Complete required IEP sections before submitting")
            report_status_service.submit_report(db, report, user, readiness_ok=True)
        elif report.report_type == "monthly":
            from sqlalchemy import select

            from app.models.clinical_report import ClinicalReportSection

            sections = list(
                db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all()
            )
            ready = report_engine_service.required_monthly_sections_complete(sections)
            if not ready:
                raise ValueError("Complete required monthly sections before submitting")
            report_status_service.submit_report(db, report, user, readiness_ok=True)
        else:
            from sqlalchemy import select

            from app.models.clinical_report import ClinicalReportSection

            sections = list(
                db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all()
            )
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
    try:
        report_status_service.approve_report(db, report, user, share_parent=payload.share_with_parent)
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


@router.get("/reports/{report_id}/clinical-brain-evidence")
def clinical_brain_evidence(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services import clinical_brain_evidence_service as brain_ev_svc

    report = _report_or_404(db, report_id)
    _case_for_user(db, user, report.case_id)
    summary = brain_ev_svc.summarize_report_evidence(db, report)
    gaps = summary.get("evidence_gaps") or []
    summary["suggested_drafts"] = [
        {"id": f"gap-{i}", "label": gap, "source_count": summary.get("materialized_event_count", 0)}
        for i, gap in enumerate(gaps[:8])
    ]
    return summary


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
    return report_engine_service.iep_summary(db, case, user)


@router.post("/cases/{case_id}/reports/iep/start")
def start_iep(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _case_for_user_write(db, user, case_id)
    try:
        report = iep_report_service.start_iep(db, case, user)
        db.commit()
        return report_engine_service.serialize_report_workspace(db, report, case)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
    if mode == "parent":
        return report_engine_service.serialize_parent_safe_iep(db, report, case)
    return report_engine_service.serialize_report_workspace(db, report, case)


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
