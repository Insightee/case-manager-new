"""Compact structured monthly case summary for AI prompts — no raw log prose."""

from __future__ import annotations

import json
from calendar import monthrange
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.clinical_evidence import SessionGoalEntry, StrategyUseEvent
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.services import goal_evidence_aggregation_service as ev_agg
from app.services import iep_plan_service as iep_svc
from app.services.clinical_insights_preview_service import build_data_preview
from app.services.clinical_workbench_service import _parse_iep_goals


def _month_bounds(month: str) -> tuple[date, date]:
    year, mo = int(month[:4]), int(month[5:7])
    last = monthrange(year, mo)[1]
    return date(year, mo, 1), date(year, mo, last)


def _evidence_strength(session_count: int, with_notes: int, strategy_links: int) -> str:
    if session_count <= 1:
        return "insufficient"
    if session_count >= 4 and with_notes >= 2 and strategy_links >= 1:
        return "strong_operational"
    if session_count >= 2 or with_notes >= 1:
        return "moderate"
    return "weak"


def build_monthly_case_summary(db: Session, case_id: int, month: str) -> dict[str, Any]:
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    preview = build_data_preview(db, case_id, month)
    start, end = _month_bounds(month)
    plan = iep_svc.get_latest_plan(db, case_id)

    sessions = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )
        .options(selectinload(TherapySession.daily_log))
    ).all()

    logs_missing_child_response = 0
    for sess in sessions:
        log = sess.daily_log
        if not log or not log.submitted_at:
            continue
        entries = db.scalars(
            select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == log.id)
        ).all()
        if entries and not any((e.response_note or "").strip() for e in entries):
            logs_missing_child_response += 1

    goals_evidence = ev_agg.build_goals_evidence_summary(db, case_id)
    goals_out: list[dict[str, Any]] = []
    for item in goals_evidence.get("goals", [])[:8]:
        goals_out.append(
            {
                "goal_id": item.get("goal_id"),
                "goal_title": item.get("label") or item.get("title") or "Goal",
                "domain": item.get("domain_key") or "unknown",
                "sessions_addressed": item.get("session_count") or item.get("sessions_count") or 0,
                "evidence_strength": item.get("evidence_strength") or "insufficient",
                "environments": [],
                "strategies_used": item.get("strategies") or [],
                "brief_evidence_points": (item.get("recent_notes") or [])[:3],
            }
        )

    strategies_evidence = ev_agg.build_strategies_evidence_summary(db, case_id)
    strategies_out: list[dict[str, Any]] = []
    for item in strategies_evidence.get("strategies", [])[:12]:
        uses = item.get("use_count") or item.get("uses") or item.get("sessions_count") or 0
        strategies_out.append(
            {
                "strategy_id": item.get("strategy_id"),
                "name": item.get("label") or item.get("name") or "Strategy",
                "uses": uses,
                "signal": "appeared_helpful" if uses >= 3 else "mixed" if uses >= 1 else "unknown",
                "linked_goals": item.get("linked_goals") or [],
                "environments": [],
                "adaptations": [],
            }
        )

    evidence_gaps: list[str] = []
    if preview["logs_missing_details"]:
        evidence_gaps.append(f"{preview['logs_missing_details']} logs need structured goal/strategy details.")
    if logs_missing_child_response:
        evidence_gaps.append(f"{logs_missing_child_response} logs missing child response.")
    if preview["parent_input_status"] in ("outdated", "unknown", "not_received"):
        evidence_gaps.append("Parent input not updated this month.")

    iep_goals = _parse_iep_goals(plan)
    for g in iep_goals:
        label = (g.get("label") or "")[:60]
        if label and not any(label.lower() in (x.get("goal_title") or "").lower() for x in goals_out):
            goals_out.append(
                {
                    "goal_id": None,
                    "goal_title": label,
                    "domain": g.get("domain_key") or "unknown",
                    "sessions_addressed": 0,
                    "evidence_strength": "insufficient",
                    "environments": [],
                    "strategies_used": [],
                    "brief_evidence_points": [],
                }
            )

    return {
        "case": {
            "case_id": case_id,
            "child_name": getattr(case, "child_name", None) or "Child",
            "service_type": getattr(case, "service_category", None),
            "current_iep_id": plan.id if plan else None,
            "therapist_id": None,
            "case_manager_id": None,
        },
        "period": {
            "month": month,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
        "sessions": {
            "available": preview["sessions_available"],
            "logs_submitted": preview["logs_submitted"],
            "missing_logs": preview["sessions_available"] - preview["logs_submitted"],
            "logs_missing_child_response": logs_missing_child_response,
            "edited_time_entries": 0,
        },
        "goals": goals_out,
        "strategies": strategies_out,
        "evidence_gaps": evidence_gaps,
        "parent_school_inputs": {
            "parent_input_status": preview["parent_input_status"],
            "school_input_status": preview["school_input_status"],
        },
    }
