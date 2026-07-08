"""Orchestrates the compact Case Insight payload — the single source of truth for the Insights tab.

Composes every analyzer in this package into the JSON shape documented in
`docs/design/stitch/insights-tab/DESIGN.md`. No AI calls happen here; this is Layer 1
(Structured Insight Engine) in full.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.clinical import CaseClinicalProfile
from app.models.clinical_evidence import IepSupportPriority
from app.models.iep_plan import IepPlan
from app.services import iep_plan_service as iep_svc
from app.services.insights import (
    collaborative_input_mapper,
    evidence_mapper,
    goal_progress_analyzer,
    next_session_focus_builder,
    strategy_response_analyzer,
    suggested_goal_strategy_engine,
)
from app.services.insights.goal_progress_analyzer import goal_card_to_insight
from app.services.insights.helpers import make_insight

_SPLIT_PATTERN = re.compile(r"[,;\n]+")


def _split_list(text: str | None, limit: int = 6) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in _SPLIT_PATTERN.split(text) if p.strip()]
    return parts[:limit]


def _goal_numeric_id(goal_id: str) -> int | None:
    if not goal_id or not goal_id.startswith("goal_"):
        return None
    tail = goal_id[len("goal_") :]
    return int(tail) if tail.isdigit() else None


def _build_child_snapshot(
    db: Session,
    case: Case,
    patterns: dict[str, list[str]],
) -> tuple[dict[str, Any], dict]:
    profile = db.scalars(select(CaseClinicalProfile).where(CaseClinicalProfile.case_id == case.id)).first()
    strengths = _split_list(profile.strengths if profile else None)
    interests = _split_list(profile.interests if profile else None)
    support_priorities = db.scalars(
        select(IepSupportPriority).where(IepSupportPriority.case_id == case.id).order_by(IepSupportPriority.sort_order)
    ).all()
    support_needs = [p.label for p in support_priorities][:6]
    helpful_supports = patterns.get("helpfulSupports") or []
    recent_pattern = (
        f"{helpful_supports[0]} has shown a positive pattern in recent sessions."
        if helpful_supports
        else "Recent sessions are still building a clear support pattern."
    )

    child_name = case.child.full_name if case.child else "This child"
    strengths_text = ", ".join(strengths[:3]) or "consistent engagement in structured activities"
    support_text = ", ".join(support_needs[:2]) or "predictable routines"
    summary_paragraph = (
        f"{child_name} participates more comfortably with predictable routines and clear supports. "
        f"Strengths include {strengths_text}. {support_text.capitalize()} still benefit from environmental support."
    )

    snapshot = {
        "childName": child_name,
        "strengthsInterests": strengths + interests,
        "helpfulSupports": helpful_supports,
        "supportNeeds": support_needs,
        "recentPattern": recent_pattern,
        "summaryParagraph": summary_paragraph,
        "sourceLine": "Source: observation report, recent session logs, parent input",
    }
    insight = make_insight(
        insight_id="child_snapshot",
        insight_type="child_snapshot",
        title=f"{child_name} — snapshot",
        summary=summary_paragraph,
        source_type="observation_report",
        source_count=1,
        source_label=snapshot["sourceLine"],
        recommended_action="Add to Monthly Report",
        review_path="therapist_review",
    )
    return snapshot, insight


def build_case_insight_payload(db: Session, case_id: int) -> dict[str, Any]:
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    plan = iep_svc.get_latest_plan(db, case_id)

    goal_cards = goal_progress_analyzer.build_goal_progress_cards(db, case_id)
    strategies_by_goal, strategy_insights = strategy_response_analyzer.build_strategy_cards_by_goal(db, case_id)
    for card in goal_cards:
        numeric_id = _goal_numeric_id(card["goalId"])
        card["strategies"] = strategies_by_goal.get(numeric_id, []) if numeric_id else []

    evidence_cards, session_patterns, evidence_insights = evidence_mapper.build_evidence_cards(db, case_id)
    collaborative_cards, collaborative_insights = collaborative_input_mapper.build_collaborative_input_cards(
        db, case_id
    )
    suggested, suggested_insights = suggested_goal_strategy_engine.build_suggested_goals_and_strategies(db, case_id)
    next_focus = next_session_focus_builder.build_next_session_focus(goal_cards, evidence_cards)

    child_snapshot, child_insight = _build_child_snapshot(db, case, session_patterns)

    goal_insights = [goal_card_to_insight(card) for card in goal_cards]
    next_focus_insight = next_session_focus_builder.next_session_focus_to_insight(next_focus)

    insights: list[dict] = [child_insight, *goal_insights, *strategy_insights, *evidence_insights]
    if next_focus_insight:
        insights.append(next_focus_insight)
    insights.extend(collaborative_insights)
    insights.extend(suggested_insights)

    payload = {
        "caseId": case_id,
        "child": child_snapshot,
        "activeIEP": {
            "iepId": plan.id if plan else None,
            "status": plan.status if plan else None,
            "goals": goal_cards,
        },
        "recentSessions": {
            "window": "last_5_sessions",
            "patterns": session_patterns,
        },
        "collaborativeInputs": collaborative_cards,
        "evidence": evidence_cards,
        "nextSessionFocus": next_focus,
        "suggested": suggested,
        "insights": insights,
    }
    return payload


def compute_input_hash(payload: dict[str, Any]) -> str:
    """Stable hash of the parts of the payload that should trigger a fresh AI refresh."""
    fingerprint = {
        "goal_ids": [g["goalId"] for g in payload["activeIEP"]["goals"]],
        "goal_statuses": [g["status"] for g in payload["activeIEP"]["goals"]],
        "strategy_ids": sorted(
            s["strategyId"] for g in payload["activeIEP"]["goals"] for s in g.get("strategies", [])
        ),
        "collaborative_ids": [c["id"] for c in payload["collaborativeInputs"]],
        "evidence_summaries": [c["summary"] for c in payload["evidence"].values()],
        "suggested_goal_ids": [g["goalId"] for g in payload["suggested"]["goals"]],
        "suggested_strategy_ids": [s["strategyId"] for s in payload["suggested"]["strategies"]],
    }
    raw = json.dumps(fingerprint, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()
