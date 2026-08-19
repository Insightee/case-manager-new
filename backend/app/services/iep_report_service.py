"""IEP report orchestration — thin layer over report engine, goals, strategies, session evidence."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_measurement_criteria import (
    GOAL_LIFECYCLE_STATUSES,
    validate_iep_goal,
    validate_measurement_fields,
)
from app.models.case import Case
from app.models.clinical_evidence import IepGoalCard
from app.models.clinical_report import (
    ClinicalReport,
    ClinicalReportSection,
    ClinicalReportStatus,
    ClinicalReportType,
    SectionCompletionStatus,
    SectionVisibility,
)
from app.models.goal_repository import GoalRepositoryItem, RepositoryItemStatus, StrategyRepositoryItem
from app.models.iep_plan import IepPlan, IepPlanStatus
from app.models.user import User
from app.report_engine_constants import IEP_REPORT_SECTIONS, REQUIRED_IEP_SECTION_KEYS
from app.services import goal_repository_service, observation_report_service, report_engine_service, report_status_service
from app.services.goals_engine_service import build_goals_engine_payload


def _json_loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _json_dumps(data: dict | list) -> str:
    return json.dumps(data)


def _new_iep_goal_id() -> str:
    return str(uuid.uuid4())


def _goals_plan_section(db: Session, report: ClinicalReport) -> ClinicalReportSection:
    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "goals_plan",
        )
    )
    if not sec:
        raise ValueError("goals_plan section not found")
    return sec


def _goals_plan_data(sec: ClinicalReportSection) -> dict:
    data = _json_loads(sec.structured_data_json)
    data.setdefault("goals", [])
    data.setdefault("pending_changes", [])
    return data


def _save_goals_plan(db: Session, report: ClinicalReport, data: dict) -> None:
    report_engine_service.patch_section(db, report, "goals_plan", structured_data=data)


def _report_metadata(report: ClinicalReport) -> dict:
    return _json_loads(report.metadata_json)


def _set_report_metadata(db: Session, report: ClinicalReport, meta: dict) -> None:
    report.metadata_json = _json_dumps(meta)
    db.flush()


def _is_approved_iep(report: ClinicalReport) -> bool:
    return report.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    )


def _can_cm_edit(report: ClinicalReport, user: User) -> bool:
    roles = {r.name for r in getattr(user, "roles", []) or []}
    if roles & {"ADMIN", "SUPER_ADMIN", "CASE_MANAGER"}:
        return True
    return report.case_manager_id == user.id


def _therapist_needs_approval(report: ClinicalReport) -> bool:
    return _is_approved_iep(report)


def _default_goal(**overrides: Any) -> dict:
    base = {
        "iep_goal_id": _new_iep_goal_id(),
        "source_goal_id": None,
        "source_type": "manual",
        "title": "",
        "goal_statement": "",
        "domain": "",
        "environments": [],
        "baseline_current_state": "",
        "desired_state": "",
        "participation": "not_yet_participating",
        "independence_support_needed": "full_adult_support",
        "goal_achievement": "baseline",
        "linked_strategy_ids": [],
        "custom_strategy_notes": "",
        "parent_facing_wording": "",
        "therapist_notes": "",
        "cm_notes": "",
        "evidence_sources": [],
        "lifecycle_status": "draft",
        "status": "draft",
    }
    base.update(overrides)
    return base


def _log_iep_event(
    db: Session,
    report: ClinicalReport,
    user: User,
    event_type: str,
    *,
    comment: str | None = None,
    metadata: dict | None = None,
) -> None:
    report_status_service.log_review_event(db, report, user, event_type, comment=comment, metadata=metadata)


def start_iep(db: Session, case: Case, user: User) -> ClinicalReport:
    existing = report_engine_service.get_active_iep_report(db, case.id)
    if existing and existing.status not in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    ):
        report_engine_service.seed_iep_sections(db, existing.id)
        return existing
    if existing and existing.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    ):
        existing.archived_at = datetime.now(timezone.utc)
        db.flush()
    child_name = case.child.full_name if case.child else "Client"
    row = ClinicalReport(
        case_id=case.id,
        child_id=case.child_id,
        report_type=ClinicalReportType.IEP.value,
        title=f"IEP Support Plan — {child_name}",
        status=ClinicalReportStatus.DRAFT.value,
        created_by_id=user.id,
        assigned_therapist_id=user.id,
        case_manager_id=case.case_manager_user_id,
    )
    db.add(row)
    db.flush()
    report_engine_service.seed_iep_sections(db, row.id)
    _log_iep_event(db, row, user, "created")
    return row


def generate_iep_draft_from_observation(db: Session, report: ClinicalReport, user: User) -> dict:
    if report.report_type != ClinicalReportType.IEP.value:
        raise ValueError("Not an IEP report")
    obs = report_engine_service.get_active_observation_report(db, report.case_id)
    warning = None
    if not obs:
        warning = "No observation report found — starting with a manual plan."
    elif obs.status not in (ClinicalReportStatus.APPROVED.value, ClinicalReportStatus.LOCKED.value):
        warning = "Observation report is not yet approved — context may be incomplete."

    child_context: dict[str, Any] = {}
    priority_domains: list[str] = []
    goals: list[dict] = []
    present_levels: dict[str, dict[str, str]] = {}
    insights: dict[str, str] = {}
    talent: dict[str, str] = {}
    env_data: dict[str, Any] = {}
    service_plan: dict[str, str] = {}

    if obs:
        obs_sections = list(
            db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == obs.id)).all()
        )
        by_key = {s.section_key: s for s in obs_sections}
        for key in ("child_snapshot", "strengths_interests", "support_needs", "referral_background"):
            sec = by_key.get(key)
            if sec and sec.narrative_text:
                child_context[key] = sec.narrative_text
            struct = _json_loads(sec.structured_data_json) if sec else {}
            if struct:
                child_context.setdefault("structured", {})[key] = struct
        rec = by_key.get("recommendations_iep")
        if rec and rec.narrative_text:
            child_context["recommendations_iep"] = rec.narrative_text
        for domain_key in ("communication", "regulation_sensory", "participation", "learning_access", "peer_interaction"):
            sec = by_key.get(domain_key)
            if sec and (sec.narrative_text or sec.completion_status == SectionCompletionStatus.COMPLETED.value):
                priority_domains.append(domain_key)
        candidates = observation_report_service.list_candidates(db, obs.id)
        obs_strategies = candidates.get("strategies", [])
        for g in candidates.get("goals", []):
            gid = g.get("id")
            domain = g.get("domain_key", "general")
            linked = [
                {"id": s["id"], "source_type": "candidate"}
                for s in obs_strategies
                if not domain or s.get("domain_key") in (domain, None) or domain == "general"
            ][:2]
            goals.append(
                _default_goal(
                    source_goal_id=gid,
                    source_type="observation_candidate" if gid else "session_log_candidate",
                    title=g.get("label", ""),
                    goal_statement=g.get("goal_statement") or g.get("label", ""),
                    domain=domain,
                    baseline_current_state=g.get("baseline_state") or g.get("rationale", ""),
                    desired_state=g.get("desired_state", ""),
                    lifecycle_status="draft",
                    linked_strategy_ids=linked,
                )
            )

        present_levels = {}
        from app.core.iep_observation_align import IEP_DOMAIN_TABS, IEP_LEARNING_ENVIRONMENTS

        support_sec = by_key.get("support_needs")
        support_snip = (support_sec.narrative_text or "")[:400] if support_sec else ""
        for tab in IEP_DOMAIN_TABS:
            obs_key = tab["id"]
            sec = by_key.get(obs_key)
            if sec and (sec.narrative_text or "").strip():
                present_levels[obs_key] = {
                    "strengths": sec.narrative_text.strip(),
                    "support_needs": support_snip,
                    "source": "observation_report",
                }

        strengths_sec = by_key.get("strengths_interests")
        strengths_struct = _json_loads(strengths_sec.structured_data_json) if strengths_sec else {}
        imported = strengths_struct.get("strengths") or []
        imported_interests = strengths_struct.get("interests") or []
        talent = {
            "imported_strengths": imported,
            "imported_interests": imported_interests,
            "strengths": ", ".join(imported) if imported else (strengths_sec.narrative_text if strengths_sec else ""),
            "opportunities": (by_key.get("recommendations_iep").narrative_text if by_key.get("recommendations_iep") else ""),
        }
        strategies_sec = by_key.get("strategies_tried")
        support_barrier = by_key.get("support_needs")
        insights = {
            "promising_strategy": (strategies_sec.narrative_text if strategies_sec else "")[:600],
            "emerging_barrier": (support_barrier.narrative_text if support_barrier else "")[:600],
        }
        env_sec = by_key.get("environment_notes")
        env_struct = _json_loads(env_sec.structured_data_json) if env_sec else {}
        env_list = env_struct.get("environments") or []
        environments: dict[str, dict] = {}
        for env_row in IEP_LEARNING_ENVIRONMENTS:
            eid = env_row["id"]
            match = next(
                (
                    e
                    for e in env_list
                    if (e.get("id") == eid or e.get("key") == eid or (e.get("label") or "").lower() == env_row["label"].lower())
                ),
                None,
            )
            environments[eid] = {
                "label": env_row["label"],
                "notes": (match or {}).get("notes") or (env_sec.narrative_text if env_sec and eid == "school_classroom" else ""),
            }
        env_data = {"environments": environments, "environments_list": env_list}
        rec = by_key.get("recommendations_iep")
        service_plan = {"plan_notes": rec.narrative_text if rec else ""}

    narrative_parts = [
        child_context.get(k)
        for k in ("child_snapshot", "referral_background", "strengths_interests", "support_needs")
        if isinstance(child_context.get(k), str) and child_context.get(k, "").strip()
    ]
    child_narrative = "\n\n".join(narrative_parts)

    report_engine_service.patch_section(
        db, report, "child_context",
        narrative_text=child_narrative,
        structured_data={
            **child_context,
            "care_team_lead": "Therapist Neha",
            "primary_setting": "School and community settings",
        },
    )
    report_engine_service.patch_section(
        db, report, "priority_domains",
        structured_data={"domains": priority_domains, "present_levels": present_levels if obs else {}},
    )
    if obs:
        report_engine_service.patch_section(db, report, "clinical_insights", structured_data=insights)
        report_engine_service.patch_section(db, report, "strategies_accommodations", structured_data=env_data)
        report_engine_service.patch_section(db, report, "talent_development", structured_data=talent)
        report_engine_service.patch_section(
            db,
            report,
            "review_parent_plan",
            narrative_text=service_plan.get("plan_notes", ""),
            structured_data=service_plan,
        )
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    if goals:
        plan_data["goals"] = goals
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    _log_iep_event(db, report, user, "edited", metadata={"action": "draft_from_observation", "warning": warning})
    return {"warning": warning, "goals_imported": len(goals), "domains": priority_domains}


def _list_session_log_goals(db: Session, case_id: int) -> list[dict]:
    from app.models.session_evidence import SessionGoalEntry
    from app.models.daily_log import DailyLog
    from app.models.session import Session as TherapySession

    rows = list(
        db.scalars(
            select(SessionGoalEntry)
            .join(DailyLog, SessionGoalEntry.daily_log_id == DailyLog.id)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(TherapySession.case_id == case_id)
            .order_by(SessionGoalEntry.id.desc())
            .limit(20)
        ).all()
    )
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        label = (row.goal_label or "").strip()
        if not label or label.lower() in seen:
            continue
        seen.add(label.lower())
        out.append(
            {
                "id": row.id,
                "label": label,
                "domain_key": row.domain_key or "general",
                "source": "session_log",
                "goal_statement": label,
            }
        )
    return out


def list_available_goals_for_iep(db: Session, case_id: int) -> dict:
    obs = report_engine_service.get_active_observation_report(db, case_id)
    obs_candidates: list[dict] = []
    if obs:
        c = observation_report_service.list_candidates(db, obs.id)
        obs_candidates = c.get("goals", []) + c.get("suggested_goals", [])
    repo = goal_repository_service.list_goal_candidates(db, case_id)
    engine = build_goals_engine_payload(db, case_id)
    session_log_goals = _list_session_log_goals(db, case_id)
    return {
        "observation_candidates": obs_candidates,
        "repository_goals": repo,
        "case_goals": engine.get("goals", []),
        "org_pool_goals": engine.get("org_pool_goals", []),
        "session_log_goals": session_log_goals,
        "active_iep_cards": engine.get("iep_goals", []),
    }


def list_available_strategies_for_iep(
    db: Session,
    case_id: int,
    *,
    goal_id: str | None = None,
    domain: str | None = None,
    environment: str | None = None,
) -> dict:
    strategies = goal_repository_service.list_strategy_candidates(db, case_id)
    engine = build_goals_engine_payload(db, case_id)
    items = strategies + engine.get("strategies", []) + engine.get("org_pool_strategies", [])
    if domain:
        items = [s for s in items if s.get("domain_key") == domain or domain in (s.get("core_domains") or [])]
    if environment:
        items = [s for s in items if environment in (s.get("core_environments") or []) or s.get("environment_context") == environment]
    return {"items": items, "goal_id": goal_id}


def _find_goal(plan_data: dict, iep_goal_id: str) -> dict | None:
    for g in plan_data.get("goals", []):
        if g.get("iep_goal_id") == iep_goal_id:
            return g
    return None


def add_goal_to_iep(
    db: Session,
    report: ClinicalReport,
    user: User,
    *,
    goal_source_id: int | None,
    source_type: str,
) -> dict:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    payload = _default_goal(source_type=source_type)
    if goal_source_id:
        row = db.get(GoalRepositoryItem, goal_source_id)
        if row:
            payload.update(
                source_goal_id=row.id,
                title=row.label,
                goal_statement=row.goal_statement or row.label,
                domain=row.domain_key,
                baseline_current_state=row.baseline_state or "",
                desired_state=row.desired_state or "",
            )
    if _therapist_needs_approval(report) and not _can_cm_edit(report, user):
        change_id = _new_iep_goal_id()
        plan_data.setdefault("pending_changes", []).append(
            {
                "change_id": change_id,
                "change_type": "add_goal",
                "iep_goal_id": payload["iep_goal_id"],
                "proposed_by_user_id": user.id,
                "proposed_at": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
                "status": "pending_review",
            }
        )
        payload["lifecycle_status"] = "pending_review"
    plan_data.setdefault("goals", []).append(payload)
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    _log_iep_event(db, report, user, "edited", metadata={"action": "goal_added", "iep_goal_id": payload["iep_goal_id"]})
    return payload


def create_manual_goal_in_iep(db: Session, report: ClinicalReport, user: User, payload: dict) -> dict:
    goal = _default_goal()
    goal.update({k: v for k, v in payload.items() if v is not None})
    goal.setdefault("iep_goal_id", _new_iep_goal_id())
    goal.setdefault("source_type", "manual")
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    if _therapist_needs_approval(report) and not _can_cm_edit(report, user):
        plan_data.setdefault("pending_changes", []).append(
            {
                "change_id": _new_iep_goal_id(),
                "change_type": "add_goal",
                "iep_goal_id": goal["iep_goal_id"],
                "proposed_by_user_id": user.id,
                "proposed_at": datetime.now(timezone.utc).isoformat(),
                "payload": goal,
                "status": "pending_review",
            }
        )
        goal["lifecycle_status"] = "pending_review"
    plan_data.setdefault("goals", []).append(goal)
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    _log_iep_event(db, report, user, "edited", metadata={"action": "manual_goal", "iep_goal_id": goal["iep_goal_id"]})
    return goal


def patch_iep_goal(db: Session, report: ClinicalReport, user: User, iep_goal_id: str, payload: dict) -> dict:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    goal = _find_goal(plan_data, iep_goal_id)
    if not goal:
        raise ValueError("Goal not found")
    if _therapist_needs_approval(report) and not _can_cm_edit(report, user):
        plan_data.setdefault("pending_changes", []).append(
            {
                "change_id": _new_iep_goal_id(),
                "change_type": "edit_goal",
                "iep_goal_id": iep_goal_id,
                "proposed_by_user_id": user.id,
                "proposed_at": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
                "status": "pending_review",
            }
        )
    else:
        goal.update(payload)
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    _log_iep_event(db, report, user, "edited", metadata={"action": "goal_patched", "iep_goal_id": iep_goal_id})
    return goal


def delete_iep_goal(db: Session, report: ClinicalReport, user: User, iep_goal_id: str) -> None:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    plan_data["goals"] = [g for g in plan_data.get("goals", []) if g.get("iep_goal_id") != iep_goal_id]
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    _log_iep_event(db, report, user, "edited", metadata={"action": "goal_deleted", "iep_goal_id": iep_goal_id})


def link_strategy_to_iep_goal(
    db: Session,
    report: ClinicalReport,
    user: User,
    iep_goal_id: str,
    strategy_id: int,
    strategy_source_type: str = "repository",
) -> dict:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    goal = _find_goal(plan_data, iep_goal_id)
    if not goal:
        raise ValueError("Goal not found")
    links = goal.setdefault("linked_strategy_ids", [])
    entry = {"id": strategy_id, "source_type": strategy_source_type}
    if entry not in links:
        links.append(entry)
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    _log_iep_event(db, report, user, "edited", metadata={"action": "strategy_linked", "iep_goal_id": iep_goal_id})
    return goal


def unlink_strategy_from_iep_goal(
    db: Session, report: ClinicalReport, user: User, iep_goal_id: str, strategy_id: int
) -> dict:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    goal = _find_goal(plan_data, iep_goal_id)
    if not goal:
        raise ValueError("Goal not found")
    goal["linked_strategy_ids"] = [
        x for x in goal.get("linked_strategy_ids", []) if x.get("id") != strategy_id and x != strategy_id
    ]
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    return goal


def create_strategy_candidate_from_iep(
    db: Session,
    report: ClinicalReport,
    user: User,
    iep_goal_id: str,
    payload: dict,
) -> dict:
    row = goal_repository_service.create_strategy_candidate(
        db,
        case_id=report.case_id,
        user_id=user.id,
        label=payload.get("label", ""),
        when_to_use=payload.get("when_to_use"),
        how_to_use=payload.get("how_to_use"),
        strategy_steps=payload.get("strategy_steps"),
        domain_key=payload.get("domain_key"),
        environment_context=payload.get("environment_context"),
        source="iep_report",
    )
    link_strategy_to_iep_goal(db, report, user, iep_goal_id, row["id"], "candidate")
    return row


def list_pending_changes(db: Session, report: ClinicalReport) -> list[dict]:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    return [c for c in plan_data.get("pending_changes", []) if c.get("status") == "pending_review"]


def approve_changes(db: Session, report: ClinicalReport, reviewer: User, change_ids: list[str]) -> dict:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    approved = 0
    for change in plan_data.get("pending_changes", []):
        if change.get("change_id") not in change_ids:
            continue
        if change.get("status") != "pending_review":
            continue
        ctype = change.get("change_type")
        payload = change.get("payload") or {}
        gid = change.get("iep_goal_id")
        if ctype == "add_goal":
            goal = _find_goal(plan_data, gid)
            if not goal:
                goal = {**_default_goal(), **payload, "iep_goal_id": gid or payload.get("iep_goal_id")}
                plan_data.setdefault("goals", []).append(goal)
            goal["lifecycle_status"] = "active"
            goal["status"] = "approved"
        elif ctype == "edit_goal":
            goal = _find_goal(plan_data, gid)
            if goal:
                goal.update(payload)
                goal["lifecycle_status"] = "active"
        elif ctype == "mark_achieved":
            goal = _find_goal(plan_data, gid)
            if goal:
                goal["lifecycle_status"] = "achieved"
        change["status"] = "approved"
        approved += 1
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    sync_approved_iep_goals_to_active_case_plan(db, report, reviewer)
    _log_iep_event(db, report, reviewer, "approved", metadata={"partial": True, "change_ids": change_ids})
    return {"approved": approved}


def return_changes(db: Session, report: ClinicalReport, reviewer: User, change_ids: list[str], comment: str) -> dict:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    returned = 0
    for change in plan_data.get("pending_changes", []):
        if change.get("change_id") in change_ids:
            change["status"] = "returned"
            change["return_comment"] = comment
            returned += 1
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    _log_iep_event(db, report, reviewer, "returned", comment=comment, metadata={"change_ids": change_ids})
    return {"returned": returned}


def mark_goal_achieved(db: Session, report: ClinicalReport, user: User, iep_goal_id: str) -> dict:
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    goal = _find_goal(plan_data, iep_goal_id)
    if not goal:
        raise ValueError("Goal not found")
    if _therapist_needs_approval(report) and not _can_cm_edit(report, user):
        plan_data.setdefault("pending_changes", []).append(
            {
                "change_id": _new_iep_goal_id(),
                "change_type": "mark_achieved",
                "iep_goal_id": iep_goal_id,
                "proposed_by_user_id": user.id,
                "proposed_at": datetime.now(timezone.utc).isoformat(),
                "payload": {},
                "status": "pending_review",
            }
        )
    else:
        goal["lifecycle_status"] = "achieved"
        goal["goal_achievement"] = "achieved_across_settings"
    sec.structured_data_json = _json_dumps(plan_data)
    db.flush()
    if goal.get("lifecycle_status") == "achieved":
        sync_approved_iep_goals_to_active_case_plan(db, report, user)
    _log_iep_event(db, report, user, "edited", metadata={"action": "mark_achieved", "iep_goal_id": iep_goal_id})
    return goal


def record_amendment(db: Session, report: ClinicalReport, user: User) -> ClinicalReport:
    if not _can_cm_edit(report, user):
        raise ValueError("Only case managers can amend approved IEP")
    meta = _report_metadata(report)
    meta["amendment_active"] = True
    meta["amendment_started_at"] = datetime.now(timezone.utc).isoformat()
    _set_report_metadata(db, report, meta)
    _log_iep_event(db, report, user, "reopened", metadata={"action": "amendment_started"})
    return report


def submit_parent_input(db: Session, report: ClinicalReport, user: User, text: str) -> dict:
    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "review_parent_plan",
        )
    )
    if not sec:
        raise ValueError("review_parent_plan section not found")
    data = _json_loads(sec.structured_data_json)
    inputs = data.setdefault("parent_inputs", [])
    entry = {
        "id": _new_iep_goal_id(),
        "text": text.strip(),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "submitted_by_parent_user_id": user.id,
        "visibility": "parent_safe",
    }
    inputs.append(entry)
    sec.structured_data_json = _json_dumps(data)
    db.flush()
    return entry


def validate_iep_submit(db: Session, report: ClinicalReport) -> dict:
    sections = list(
        db.scalars(select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)).all()
    )
    by_key = {s.section_key: s for s in sections}
    errors: list[str] = []
    warnings: list[str] = []

    ctx = by_key.get("child_context")
    if not ctx or (not (ctx.narrative_text or "").strip() and not _json_loads(ctx.structured_data_json)):
        errors.append("child_context")

    domains = by_key.get("priority_domains")
    dom_data = _json_loads(domains.structured_data_json) if domains else {}
    if not dom_data.get("domains"):
        errors.append("priority_domains")

    goals_sec = by_key.get("goals_plan")
    plan = _json_loads(goals_sec.structured_data_json) if goals_sec else {}
    goals = [g for g in plan.get("goals", []) if g.get("lifecycle_status") not in ("achieved", "closed", "revised")]
    if not goals:
        errors.append("goals_plan")
    for g in goals:
        g_errors = validate_iep_goal(g)
        if g_errors:
            errors.append(f"goal:{g.get('iep_goal_id')}:{'|'.join(g_errors)}")

    for g in goals:
        if not g.get("linked_strategy_ids") and not (g.get("custom_strategy_notes") or "").strip():
            warnings.append(f"goal:{g.get('iep_goal_id')}:missing_strategy")

    return {
        "ready": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "strategy_warning": bool(warnings),
    }


def sync_approved_iep_goals_to_active_case_plan(db: Session, report: ClinicalReport, actor: User) -> dict:
    if report.report_type != ClinicalReportType.IEP.value:
        raise ValueError("Not an IEP report")
    plan_row = db.scalar(
        select(IepPlan).where(IepPlan.case_id == report.case_id).order_by(IepPlan.id.desc())
    )
    if not plan_row:
        plan_row = IepPlan(
            case_id=report.case_id,
            version="v1",
            status=IepPlanStatus.APPROVED.value,
            created_by_user_id=actor.id,
        )
        db.add(plan_row)
        db.flush()
    elif plan_row.status == IepPlanStatus.DRAFT.value:
        plan_row.status = IepPlanStatus.APPROVED.value

    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    synced = 0
    report_approved = report.status in (
        ClinicalReportStatus.APPROVED.value,
        ClinicalReportStatus.LOCKED.value,
    )
    for i, goal in enumerate(plan_data.get("goals", [])):
        lifecycle = goal.get("lifecycle_status") or goal.get("status", "draft")
        if lifecycle in ("pending_review", "revised", "closed"):
            continue
        if lifecycle == "draft" and not report_approved:
            continue
        if lifecycle == "achieved":
            card_status = "achieved"
        else:
            card_status = "active"
            goal["lifecycle_status"] = "active"
        repo_id = goal.get("source_goal_id")
        iep_gid = goal.get("iep_goal_id")
        existing = None
        if repo_id:
            existing = db.scalar(
                select(IepGoalCard).where(
                    IepGoalCard.case_id == report.case_id,
                    IepGoalCard.repository_item_id == repo_id,
                )
            )
        if not existing and iep_gid:
            cards = db.scalars(select(IepGoalCard).where(IepGoalCard.case_id == report.case_id)).all()
            for c in cards:
                settings = _json_loads(c.settings_json)
                if settings.get("iep_goal_id") == iep_gid:
                    existing = c
                    break
        label = goal.get("title") or goal.get("goal_statement") or "Goal"
        settings = {
            "iep_goal_id": iep_gid,
            "clinical_report_id": report.id,
            "participation": goal.get("participation"),
            "independence_support_needed": goal.get("independence_support_needed"),
            "goal_achievement": goal.get("goal_achievement"),
            "lifecycle_status": lifecycle,
        }
        if existing:
            existing.label = label
            existing.goal_statement = goal.get("goal_statement") or label
            existing.baseline = goal.get("baseline_current_state")
            existing.domain_key = goal.get("domain") or existing.domain_key
            existing.status = card_status
            existing.settings_json = _json_dumps(settings)
            if repo_id:
                existing.repository_item_id = repo_id
        else:
            db.add(
                IepGoalCard(
                    iep_plan_id=plan_row.id,
                    case_id=report.case_id,
                    domain_key=goal.get("domain") or "general",
                    label=label,
                    goal_statement=goal.get("goal_statement") or label,
                    baseline=goal.get("baseline_current_state"),
                    status=card_status,
                    repository_item_id=repo_id,
                    sort_order=i,
                    settings_json=_json_dumps(settings),
                )
            )
        synced += 1
    db.flush()
    _log_iep_event(db, report, actor, "approved", metadata={"action": "sync_active_plan", "synced": synced})
    return {"synced": synced, "iep_plan_id": plan_row.id}


def get_iep_goal_progress_snapshot(db: Session, case_id: int, month_start: date, month_end: date) -> dict:
    from app.models.session_evidence import SessionGoalEntry, StrategyUseEvent
    from app.models.daily_log import DailyLog
    from app.models.session import Session as TherapySession

    cards = list(
        db.scalars(
            select(IepGoalCard).where(IepGoalCard.case_id == case_id, IepGoalCard.status == "active")
        ).all()
    )
    goals_out = []
    for card in cards:
        settings = _json_loads(card.settings_json)
        entries = list(
            db.scalars(
                select(SessionGoalEntry).where(SessionGoalEntry.goal_card_id == card.id)
            ).all()
        )
        goals_out.append(
            {
                "goal_card_id": card.id,
                "iep_goal_id": settings.get("iep_goal_id"),
                "label": card.label,
                "participation": settings.get("participation"),
                "independence_support_needed": settings.get("independence_support_needed"),
                "goal_achievement": settings.get("goal_achievement"),
                "session_count": len(entries),
                "latest_participation": getattr(entries[-1], "participation", None) if entries else None,
                "evidence_snippets": [],
                "missing_evidence": len(entries) == 0,
            }
        )
    return {"goals": goals_out, "month_start": month_start.isoformat(), "month_end": month_end.isoformat()}


def get_iep_progress_review_snapshot(db: Session, case_id: int, from_date: date, to_date: date) -> dict:
    reports = list(
        db.scalars(
            select(ClinicalReport).where(
                ClinicalReport.case_id == case_id,
                ClinicalReport.report_type == ClinicalReportType.IEP.value,
            )
        ).all()
    )
    versions = [
        {
            "report_id": r.id,
            "status": r.status,
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        }
        for r in reports
    ]
    return {
        "iep_versions": versions,
        "goals_continued": [],
        "goals_revised": [],
        "goals_achieved": [],
        "monthly_snapshots": [],
        "strategy_usage_summary": [],
        "review_questions": [
            "Which active goals still reflect the child's current support needs?",
            "Are any goals ready to mark achieved or revise?",
        ],
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
    }


def generate_iep_suggestions(db: Session, report: ClinicalReport, case: Case) -> dict:
    """Layer 1 deterministic suggestions — on-demand only."""
    sec = _goals_plan_section(db, report)
    plan_data = _goals_plan_data(sec)
    suggestions = []
    for g in plan_data.get("goals", []):
        if not (g.get("baseline_current_state") or "").strip():
            suggestions.append(
                {
                    "type": "missing_info",
                    "target_section": "goals_plan",
                    "target_goal_id": g.get("iep_goal_id"),
                    "text": "Add a baseline / current state for this goal before CM review.",
                    "source_refs": [],
                    "confidence": "high",
                    "action": "review",
                }
            )
        if not g.get("linked_strategy_ids") and not g.get("custom_strategy_notes"):
            suggestions.append(
                {
                    "type": "strategy_match",
                    "target_section": "goals_plan",
                    "target_goal_id": g.get("iep_goal_id"),
                    "text": "Consider linking a strategy or support note for this goal.",
                    "source_refs": [],
                    "confidence": "medium",
                    "action": "review",
                }
            )
    return {"suggestions": suggestions}


def _filter_repository_items(items: list[dict], *, q: str = "", domain: str | None = None) -> list[dict]:
    q_lower = (q or "").strip().lower()
    out = list(items)
    if domain:
        out = [
            i
            for i in out
            if i.get("domain_key") == domain
            or domain in (i.get("core_domains") or [])
        ]
    if q_lower:
        def _hay(item: dict) -> str:
            parts = [
                item.get("label") or "",
                item.get("goal_statement") or "",
                item.get("description") or "",
                item.get("how_to_use") or "",
                item.get("rationale") or "",
            ]
            return " ".join(parts).lower()

        out = [i for i in out if q_lower in _hay(i)]
    return out


def search_clinical_repository(
    db: Session,
    case_id: int,
    *,
    q: str = "",
    kind: str = "goals",
    domain: str | None = None,
) -> dict:
    """Unified template search for goal modal — goals or strategies."""
    kind_norm = (kind or "goals").strip().lower()
    if kind_norm == "strategies":
        pool = list_available_strategies_for_iep(db, case_id)
        items = _filter_repository_items(pool.get("items") or [], q=q, domain=domain)
        return {"kind": "strategies", "items": items, "total": len(items)}
    goals_pool = list_available_goals_for_iep(db, case_id)
    merged: list[dict] = []
    for key in ("observation_candidates", "repository_goals", "case_goals", "org_pool_goals", "session_log_goals", "active_iep_cards"):
        for row in goals_pool.get(key) or []:
            merged.append({**row, "_pool": key})
    items = _filter_repository_items(merged, q=q, domain=domain)
    return {"kind": "goals", "items": items, "total": len(items)}


def generate_goal_strategy_drafts(db: Session, report: ClinicalReport, case: Case) -> dict:
    """On-demand goal+strategy draft pairs for AI Assisted tab (Layer 1 deterministic)."""
    goals_pool = list_available_goals_for_iep(db, case.id)
    strat_pool = list_available_strategies_for_iep(db, case.id)
    candidates: list[dict] = []
    for key in ("observation_candidates", "repository_goals", "case_goals"):
        candidates.extend(goals_pool.get(key) or [])
    seen: set[str] = set()
    drafts: list[dict] = []
    for g in candidates:
        label = (g.get("label") or g.get("goal_statement") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        domain = g.get("domain_key") or (g.get("core_domains") or ["general"])[0]
        matches = [
            s
            for s in strat_pool.get("items") or []
            if s.get("domain_key") == domain or domain in (s.get("core_domains") or [])
        ][:3]
        drafts.append(
            {
                "goal": {
                    "label": label,
                    "goal_statement": g.get("goal_statement") or label,
                    "domain_key": domain,
                    "baseline_state": g.get("baseline_state") or g.get("baseline_note") or "",
                    "desired_state": g.get("desired_state") or g.get("desired_direction") or "",
                    "source_id": g.get("id"),
                    "source_type": g.get("_pool") or "repository",
                },
                "strategies": [
                    {
                        "id": s.get("id"),
                        "label": s.get("label"),
                        "description": s.get("description") or s.get("how_to_use") or "",
                    }
                    for s in matches
                ],
            }
        )
        if len(drafts) >= 5:
            break
    return {"drafts": drafts, "ai_used": False}
