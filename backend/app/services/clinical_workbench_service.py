"""Rule-based clinical documentation quality and workbench aggregations (no AI)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.case_document import CaseDocument, statuses_awaiting_cm_review
from app.models.clinical import ObservationChecklist, ObservationChecklistStatus
from app.models.clinical_evidence import GoalEvidenceEvent, SessionGoalEntry, StrategyUseEvent
from app.models.report import MonthlyReport, ReportCategory, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.iep_plan import IepPlan, IepPlanStatus
from app.models.goal_repository import RepositoryItemStatus
from app.services import goal_repository_service as repo_svc
from app.services import iep_plan_service as iep_svc
from app.services import observation_checklist_service as obs_svc
from app.services.admin_scope_service import apply_case_scope

ACTIVE_IEP_STATUSES = frozenset(
    {
        IepPlanStatus.SHARED_WITH_PARENT.value,
        IepPlanStatus.PARENT_ACKNOWLEDGED.value,
        IepPlanStatus.APPROVED.value,
    }
)

GOALS_STALE_SESSION_COUNT = 3


def _current_month_label() -> str:
    return datetime.now(timezone.utc).strftime("%B %Y")


def _status_val(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _parse_iep_goals(plan: IepPlan | None) -> list[dict[str, Any]]:
    if not plan or not plan.sections_json:
        return []
    try:
        from app.schemas.iep_plan import IepPlanSections

        data = json.loads(plan.sections_json)
        sections = IepPlanSections.model_validate(data)
        goals: list[dict[str, Any]] = []
        for block, domain in (
            (sections.talent_development, "strengths_interests"),
            (sections.other_areas_of_need, "academics_learning"),
        ):
            text = (block.goals or "").strip()
            if text:
                goals.append({"label": text, "domain_key": domain, "source": "iep_sections"})
        return goals
    except Exception:
        return []


def build_reports_workbench(db: Session, case: Case, user) -> dict[str, Any]:
    checklist = obs_svc.get_or_create_checklist(db, case, user.id)
    plan = iep_svc.get_latest_plan(db, case.id)
    reports = db.scalars(
        select(MonthlyReport).where(MonthlyReport.case_id == case.id).order_by(MonthlyReport.id.desc())
    ).all()
    return {
        "case_id": case.id,
        "observation": obs_svc.checklist_to_dict(db, checklist, case, user),
        "iep_plan_status": plan.status if plan else None,
        "monthly_reports": [
            {
                "id": r.id,
                "month": r.month,
                "status": _status_val(r.status),
                "category": r.category,
            }
            for r in reports
        ],
    }


def build_clinical_quality_summary(db: Session, case_id: int) -> dict[str, Any]:
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    month_label = _current_month_label()
    plan = iep_svc.get_latest_plan(db, case_id)
    checklist_row = db.scalars(
        select(ObservationChecklist).where(ObservationChecklist.case_id == case_id)
    ).first()
    obs_status = _status_val(checklist_row.status) if checklist_row else None

    monthly_reports = db.scalars(
        select(MonthlyReport)
        .where(MonthlyReport.case_id == case_id)
        .order_by(MonthlyReport.id.desc())
    ).all()
    client_monthly = [
        r
        for r in monthly_reports
        if (r.category or ReportCategory.CLIENT_MONTHLY.value) != ReportCategory.PROGRESS.value
    ]

    current_month_report = next((r for r in client_monthly if r.month == month_label), None)
    rejected_reports = [r for r in client_monthly if r.status == ReportStatus.REJECTED]
    pending_review = [r for r in client_monthly if r.status == ReportStatus.UNDER_REVIEW]
    published_reports = [r for r in client_monthly if r.status == ReportStatus.PUBLISHED]

    sessions = db.scalars(
        select(TherapySession)
        .where(TherapySession.case_id == case_id, TherapySession.status == SessionStatus.COMPLETED)
        .order_by(TherapySession.scheduled_date.desc(), TherapySession.id.desc())
        .limit(50)
        .options(selectinload(TherapySession.daily_log))
    ).all()

    missing_logs: list[dict] = []
    sessions_without_goal_entries: list[dict] = []
    goal_entries_without_strategy: list[dict] = []
    strategies_without_outcome: list[dict] = []
    log_ids: list[int] = []

    for sess in sessions:
        log = sess.daily_log
        if not log or not log.submitted_at:
            missing_logs.append({"session_id": sess.id, "date": sess.scheduled_date.isoformat()})
            continue
        log_ids.append(log.id)
        goal_entries = db.scalars(
            select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id)
        ).all()
        if not goal_entries and not (log.goals_addressed or "").strip():
            sessions_without_goal_entries.append({"session_id": sess.id, "daily_log_id": log.id})
        elif goal_entries:
            strategies = db.scalars(
                select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == log.id)
            ).all()
            if not strategies:
                goal_entries_without_strategy.append({"daily_log_id": log.id})
            for s in strategies:
                if not (s.outcome_note or "").strip():
                    strategies_without_outcome.append(
                        {"strategy_event_id": s.id, "label": s.strategy_label}
                    )

    evidence_by_domain = dict(
        db.execute(
            select(GoalEvidenceEvent.domain_key, func.count())
            .where(GoalEvidenceEvent.case_id == case_id)
            .group_by(GoalEvidenceEvent.domain_key)
        ).all()
    )

    iep_goals = _parse_iep_goals(plan)
    recent_log_ids = log_ids[:GOALS_STALE_SESSION_COUNT]
    stale_goals: list[dict] = []
    if iep_goals and recent_log_ids:
        recent_labels = {
            e.goal_label.lower()
            for e in db.scalars(
                select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id.in_(recent_log_ids))
            ).all()
        }
        for g in iep_goals:
            label = (g.get("label") or "")[:80]
            if label and not any(
                label.lower() in rl or rl in label.lower() for rl in recent_labels
            ):
                stale_goals.append({"label": label, "domain_key": g.get("domain_key")})

    goal_candidates = repo_svc.list_goal_candidates(db, case_id)
    strategy_candidates = repo_svc.list_strategy_candidates(db, case_id)
    pending_goals = [
        g
        for g in goal_candidates
        if g["status"] in (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)
    ]
    pending_strategies = [
        s
        for s in strategy_candidates
        if s["status"] in (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)
    ]

    missing_items: list[str] = []
    if not plan or plan.status not in ACTIVE_IEP_STATUSES:
        missing_items.append("active_iep")
    if obs_status in (
        None,
        ObservationChecklistStatus.DRAFT.value,
        ObservationChecklistStatus.REJECTED.value,
    ):
        missing_items.append("observation_checklist")
    if not current_month_report:
        missing_items.append("monthly_report_current_month")
    if missing_logs:
        missing_items.append("session_logs")
    if sessions_without_goal_entries:
        missing_items.append("session_goal_evidence")
    if pending_goals or pending_strategies:
        missing_items.append("custom_items_pending_review")

    risk_level = "ok"
    if rejected_reports or obs_status == ObservationChecklistStatus.REJECTED.value:
        risk_level = "urgent"
    elif missing_items or pending_review:
        risk_level = "attention"

    if rejected_reports:
        documentation_status = "needs_revision"
    elif missing_items:
        documentation_status = "in_progress"
    else:
        documentation_status = "complete"

    recommended: list[str] = []
    if not plan or plan.status not in ACTIVE_IEP_STATUSES:
        recommended.append("Create active IEP")
    if obs_status in (
        None,
        ObservationChecklistStatus.DRAFT.value,
        ObservationChecklistStatus.REJECTED.value,
    ):
        recommended.append("Complete observation checklist")
    if sessions_without_goal_entries or stale_goals:
        recommended.append("Add goal evidence to recent session logs")
    if pending_strategies:
        recommended.append("Review custom strategy candidates")
    if pending_goals:
        recommended.append("Review custom goal candidates")
    if not current_month_report:
        recommended.append("Generate monthly report draft")
    elif current_month_report.status in (ReportStatus.DRAFT, ReportStatus.REJECTED):
        recommended.append("Submit monthly report for CM review")
    if rejected_reports:
        recommended.append("Revise rejected monthly report")

    goal_coverage = []
    for g in iep_goals:
        label = (g.get("label") or "")[:120]
        count = 0
        for lid in log_ids:
            entries = db.scalars(
                select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == lid)
            ).all()
            if any(label.lower() in (e.goal_label or "").lower() for e in entries):
                count += 1
        goal_coverage.append(
            {
                "label": label,
                "domain_key": g.get("domain_key"),
                "sessions_addressed": count,
                "stale": any(s["label"] == label[:80] for s in stale_goals),
            }
        )

    return {
        "case_id": case_id,
        "documentation_status": documentation_status,
        "risk_level": risk_level,
        "missing_items": missing_items,
        "evidence_summary": {
            "evidence_events_by_domain": evidence_by_domain,
            "total_evidence_events": sum(evidence_by_domain.values()) if evidence_by_domain else 0,
            "sessions_without_goal_entries": len(sessions_without_goal_entries),
            "strategies_without_outcome": len(strategies_without_outcome),
        },
        "report_statuses": {
            "current_month": month_label,
            "current_month_status": _status_val(current_month_report.status)
            if current_month_report
            else None,
            "rejected_count": len(rejected_reports),
            "pending_review_count": len(pending_review),
            "published_count": len(published_reports),
            "observation_status": obs_status,
            "iep_status": plan.status if plan else None,
            "has_active_iep": bool(plan and plan.status in ACTIVE_IEP_STATUSES),
        },
        "goal_coverage": goal_coverage,
        "strategy_coverage": {
            "pending_custom_count": len(pending_strategies),
            "goal_entries_without_strategy": len(goal_entries_without_strategy),
        },
        "custom_items_pending_review": {
            "goals": pending_goals,
            "strategies": pending_strategies,
        },
        "recommended_next_actions": recommended,
        "report_timeline": [
            {
                "type": "monthly",
                "id": r.id,
                "month": r.month,
                "status": _status_val(r.status),
            }
            for r in client_monthly[:6]
        ],
    }


def build_admin_clinical_dashboard(db: Session, user, *, limit: int = 100) -> dict[str, Any]:
    stmt = select(Case).where(Case.status == "ACTIVE").order_by(Case.id.desc()).limit(limit)
    stmt = apply_case_scope(stmt, user)
    cases = db.scalars(stmt).all()
    rows = []
    for case in cases:
        try:
            summary = build_clinical_quality_summary(db, case.id)
            rows.append(
                {
                    "case_id": case.id,
                    "case_code": case.case_code,
                    "child_name": case.child_name,
                    "risk_level": summary["risk_level"],
                    "documentation_status": summary["documentation_status"],
                    "missing_items": summary["missing_items"],
                    "recommended_next_actions": summary["recommended_next_actions"][:3],
                }
            )
        except Exception:
            continue
    urgent = [r for r in rows if r["risk_level"] == "urgent"]
    attention = [r for r in rows if r["risk_level"] == "attention"]
    return {
        "total_cases": len(rows),
        "urgent_count": len(urgent),
        "attention_count": len(attention),
        "cases": rows,
    }


def build_clinical_quality_dashboard_summary(db: Session, user) -> dict[str, Any]:
    dashboard = build_admin_clinical_dashboard(db, user, limit=500)
    ok_count = sum(
        1
        for c in dashboard["cases"]
        if c["risk_level"] == "ok"
    )
    return {
        "total_cases": dashboard["total_cases"],
        "urgent_count": dashboard["urgent_count"],
        "attention_count": dashboard["attention_count"],
        "ok_count": ok_count,
        "documentation_breakdown": {
            "complete": sum(1 for c in dashboard["cases"] if c["documentation_status"] == "complete"),
            "in_progress": sum(1 for c in dashboard["cases"] if c["documentation_status"] == "in_progress"),
            "needs_revision": sum(1 for c in dashboard["cases"] if c["documentation_status"] == "needs_revision"),
        },
    }


def build_clinical_quality_dashboard_cases(
    db: Session,
    user,
    *,
    risk_level: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    dashboard = build_admin_clinical_dashboard(db, user, limit=limit)
    cases = dashboard["cases"]
    if risk_level:
        cases = [c for c in cases if c["risk_level"] == risk_level]
    return {"total": len(cases), "cases": cases}


def build_clinical_quality_dashboard_therapists(db: Session, user, *, limit: int = 100) -> dict[str, Any]:
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.user import User

    dashboard = build_admin_clinical_dashboard(db, user, limit=limit)
    case_ids = [c["case_id"] for c in dashboard["cases"]]
    if not case_ids:
        return {"therapists": []}

    assignments = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id.in_(case_ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()

    by_therapist: dict[int, dict] = {}
    case_risk = {c["case_id"]: c["risk_level"] for c in dashboard["cases"]}
    for asg in assignments:
        tid = asg.therapist_user_id
        bucket = by_therapist.setdefault(
            tid,
            {
                "therapist_user_id": tid,
                "case_count": 0,
                "urgent_count": 0,
                "attention_count": 0,
            },
        )
        bucket["case_count"] += 1
        risk = case_risk.get(asg.case_id, "ok")
        if risk == "urgent":
            bucket["urgent_count"] += 1
        elif risk == "attention":
            bucket["attention_count"] += 1

    therapists = []
    for tid, row in by_therapist.items():
        u = db.get(User, tid)
        therapists.append(
            {
                **row,
                "therapist_name": u.full_name if u and hasattr(u, "full_name") else (u.email if u else ""),
            }
        )
    therapists.sort(key=lambda t: (-t["urgent_count"], -t["attention_count"], t["therapist_name"] or ""))
    return {"therapists": therapists}
