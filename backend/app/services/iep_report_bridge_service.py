"""Bridge legacy iep_plans structured data to clinical_reports IEP lifecycle.

iep_plans = active structured plan/goals (case profile panels).
clinical_reports(type=iep) = report lifecycle, approval, parent visibility.
See docs/REPORT_ARCHITECTURE.md.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.clinical_report import ClinicalReportStatus
from app.models.iep_plan import IepPlan, IepPlanStatus
from app.models.user import User
from app.services import iep_report_service, report_engine_service, report_status_service

logger = logging.getLogger(__name__)

PARENT_VISIBLE_PLAN_STATUSES = frozenset({
    IepPlanStatus.SHARED_WITH_PARENT.value,
    IepPlanStatus.PARENT_ACKNOWLEDGED.value,
    IepPlanStatus.APPROVED.value,
})


def build_iep_report_sections_from_plan(db: Session, plan: IepPlan) -> dict[str, str]:
    """Map iep_plans sections_json into engine section narratives."""
    sections = json.loads(plan.sections_json) if plan.sections_json else {}
    if not isinstance(sections, dict):
        return {}
    mapping = {
        "child_context": sections.get("child_profile") or sections.get("child_context"),
        "priority_domains": sections.get("present_levels") or sections.get("priority_domains"),
        "goals_plan": sections.get("goals") or sections.get("goals_plan"),
        "strategies_accommodations": sections.get("environments") or sections.get("strategies_accommodations"),
        "review_parent_plan": sections.get("service_plan") or sections.get("review_parent_plan"),
        "clinical_insights": sections.get("clinical_insights"),
        "talent_development": sections.get("talent_development"),
        "internal_cm_notes": sections.get("internal_cm_notes"),
    }
    out: dict[str, str] = {}
    for key, val in mapping.items():
        if val is None:
            continue
        if isinstance(val, str):
            out[key] = val
        else:
            out[key] = json.dumps(val)
    return out


def sync_iep_plan_to_clinical_report(
    db: Session,
    plan: IepPlan,
    *,
    actor: User | None = None,
) -> None:
    """Mirror shared/approved IEP plan into clinical_reports(type=iep) when parent-visible."""
    if plan.status not in PARENT_VISIBLE_PLAN_STATUSES:
        return
    from app.services import case_service

    case = case_service.get_case(db, plan.case_id)
    if not case:
        return
    user = actor or db.get(User, plan.created_by_user_id)
    if not user:
        return
    try:
        report = report_engine_service.get_active_iep_report(db, plan.case_id)
        if not report:
            report = iep_report_service.start_iep(db, case, user)
        meta = json.loads(report.metadata_json) if report.metadata_json else {}
        meta["iep_plan_id"] = plan.id
        meta["synced_from_plan_at"] = datetime.now(timezone.utc).isoformat()
        report.metadata_json = json.dumps(meta)

        section_content = build_iep_report_sections_from_plan(db, plan)
        report_engine_service.seed_iep_sections(db, report.id)
        for key, text in section_content.items():
            try:
                report_engine_service.patch_section(db, report, key, narrative_text=text)
            except ValueError:
                continue

        if plan.status in (IepPlanStatus.PARENT_ACKNOWLEDGED.value, IepPlanStatus.APPROVED.value):
            report.status = ClinicalReportStatus.LOCKED.value
            report.parent_visible_at = plan.published_at or datetime.now(timezone.utc)
            report.locked_at = report.parent_visible_at
        elif plan.status == IepPlanStatus.SHARED_WITH_PARENT.value:
            report.status = ClinicalReportStatus.APPROVED.value
            report.parent_visible_at = plan.published_at or datetime.now(timezone.utc)
            report.approved_at = report.parent_visible_at

        if actor and report.status in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value):
            report_status_service.create_approved_version_snapshot(db, report, actor)

        db.flush()
    except Exception:
        logger.exception("iep plan sync failed plan_id=%s", plan.id)


def sync_iep_plan_best_effort(db: Session, plan: IepPlan, actor: User | None = None) -> None:
    try:
        sync_iep_plan_to_clinical_report(db, plan, actor=actor)
    except Exception:
        logger.exception("iep plan sync best-effort failed plan_id=%s", plan.id)
