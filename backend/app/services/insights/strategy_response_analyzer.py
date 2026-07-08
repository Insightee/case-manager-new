"""Per-strategy response cards, nested under IEP goal cards — reuses goal_evidence_aggregation_service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services import goal_evidence_aggregation_service as evidence_svc
from app.services.insights.helpers import make_insight, source_line, strategy_response_label


def build_strategy_cards_by_goal(db: Session, case_id: int) -> tuple[dict[int, list[dict[str, Any]]], list[dict]]:
    """Returns ({iep_goal_card_id: [strategy_card, ...]}, flat_insight_objects)."""
    summary = evidence_svc.build_strategies_evidence_summary(db, case_id)
    by_goal: dict[int, list[dict[str, Any]]] = {}
    insights: list[dict] = []

    for s in summary.get("strategies", []):
        label = s.get("label") or "Strategy"
        use_count = s.get("use_count") or 0
        response = strategy_response_label(s.get("feedback_distribution"), use_count)
        strategy_id = f"strategy_{s.get('strategy_id')}" if s.get("strategy_id") else f"strategy_local_{label[:24]}"
        card = {
            "strategyId": strategy_id,
            "label": label,
            "response": response,
            "usedInSessions": use_count,
            "whereItHelped": s.get("where_helped") or "",
            "whereNeedsAdapting": s.get("where_needs_adapting") or "",
            "evidenceSourceLine": source_line("session log", use_count),
            "status": "Case-specific strategy" if not s.get("strategy_id") else None,
        }
        linked_goal_ids = s.get("linked_goal_ids") or []
        if not linked_goal_ids:
            continue
        for gid in linked_goal_ids:
            by_goal.setdefault(gid, []).append(card)

        summary_text = card["whereItHelped"] or card["whereNeedsAdapting"] or f"{label} used in {use_count} session(s)."
        insights.append(
            make_insight(
                insight_id=f"{strategy_id}_response",
                insight_type="strategy_response",
                title=label,
                summary=summary_text,
                status=response,
                source_type="session_logs",
                source_count=use_count,
                linked_strategy_id=strategy_id,
                recommended_action="Continue" if response == "Helpful" else "Adapt",
                review_path="cm_review" if response == "Needs adapting" else "therapist_review",
            )
        )
    return by_goal, insights
