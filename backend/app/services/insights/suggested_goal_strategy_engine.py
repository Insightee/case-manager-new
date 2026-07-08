"""Suggested Goals & Strategies — draft repository items pending CM/clinical review.

Reuses `goal_repository_service.list_pending_for_case`, which already filters to LOCAL/CANDIDATE
status (never surfaces already-active/approved items as "suggested").
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services import goal_repository_service as repo_svc
from app.services import strategy_repository_stats_service as stats_svc
from app.services.insights.helpers import make_insight, suggested_goal_status, suggested_strategy_status

POOL_CANDIDATE_HELPFUL_THRESHOLD = 3


def build_suggested_goals_and_strategies(db: Session, case_id: int) -> tuple[dict[str, list[dict]], list[dict]]:
    pending = repo_svc.list_pending_for_case(db, case_id)

    suggested_goals: list[dict[str, Any]] = []
    for g in pending.get("goals", []):
        status = suggested_goal_status(g.get("status"))
        suggested_goals.append(
            {
                "goalId": f"suggested_goal_{g['id']}",
                "label": g.get("label"),
                "domainKey": g.get("domain_key"),
                "rationale": g.get("rationale") or g.get("goal_statement"),
                "status": status,
                "note": "Case-specific first. Can enter the goal pool after CM/clinical review.",
            }
        )

    suggested_strategies: list[dict[str, Any]] = []
    for s in pending.get("strategies", []):
        stats = stats_svc.aggregate_usage_for_strategy(db, s["id"]) if s.get("id") else {}
        helpful_count = stats.get("helpful_count", 0)
        status = suggested_strategy_status(s.get("status"), helpful_count, POOL_CANDIDATE_HELPFUL_THRESHOLD)
        suggested_strategies.append(
            {
                "strategyId": f"suggested_strategy_{s['id']}",
                "label": s.get("label"),
                "whenToUse": s.get("when_to_use"),
                "howToUse": s.get("how_to_use"),
                "status": status,
                "note": "Case-specific first. Can enter the strategy pool after CM/clinical review.",
            }
        )

    insights: list[dict] = []
    for g in suggested_goals:
        insights.append(
            make_insight(
                insight_id=g["goalId"],
                insight_type="suggested_goal",
                title=g["label"] or "Suggested goal",
                summary=g.get("rationale") or f"Draft goal suggested from case activity: {g['label']}",
                status=g["status"],
                source_type="repository",
                source_count=1,
                linked_goal_id=g["goalId"],
                recommended_action="Save as Draft Goal",
                review_path="iep_review",
            )
        )
    for s in suggested_strategies:
        insights.append(
            make_insight(
                insight_id=s["strategyId"],
                insight_type="suggested_strategy",
                title=s["label"] or "Suggested strategy",
                summary=s.get("howToUse") or f"Case-specific strategy candidate: {s['label']}",
                status=s["status"],
                source_type="repository",
                source_count=1,
                linked_strategy_id=s["strategyId"],
                recommended_action="Try next session",
                review_path="cm_review",
            )
        )

    return {"goals": suggested_goals, "strategies": suggested_strategies}, insights
