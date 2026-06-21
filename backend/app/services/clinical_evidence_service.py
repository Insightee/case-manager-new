from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import (
    GoalEvidenceEvent,
    SessionGoalEntry,
    StrategyUseEvent,
)
from app.models.daily_log import DailyLog


def entries_for_log(db: Session, daily_log_id: int) -> dict:
    goals = db.scalars(select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == daily_log_id)).all()
    strategies = db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == daily_log_id)).all()
    return {
        "goals": [
            {
                "id": g.id,
                "goal_card_id": g.goal_card_id,
                "goal_label": g.goal_label,
                "domain_key": g.domain_key,
                "support_level": g.support_level,
                "response_note": g.response_note,
                "visibility": g.visibility,
            }
            for g in goals
        ],
        "strategies": [
            {
                "id": s.id,
                "strategy_id": s.strategy_id,
                "strategy_label": s.strategy_label,
                "outcome_note": s.outcome_note,
            }
            for s in strategies
        ],
    }


def save_session_evidence(
    db: Session,
    *,
    daily_log: DailyLog,
    case_id: int,
    goals: list[dict],
    strategies: list[dict],
) -> dict:
    existing_goals = db.scalars(
        select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id == daily_log.id)
    ).all()
    for g in existing_goals:
        db.delete(g)
    existing_strats = db.scalars(
        select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id == daily_log.id)
    ).all()
    for s in existing_strats:
        db.delete(s)

    goal_labels: list[str] = []
    for item in goals:
        label = (item.get("goal_label") or "").strip()
        if not label:
            continue
        goal_labels.append(label)
        entry = SessionGoalEntry(
            daily_log_id=daily_log.id,
            goal_card_id=item.get("goal_card_id"),
            goal_label=label,
            domain_key=item.get("domain_key"),
            support_level=item.get("support_level"),
            response_note=item.get("response_note"),
            visibility=item.get("visibility") or "INTERNAL_ONLY",
        )
        db.add(entry)
        db.add(
            GoalEvidenceEvent(
                case_id=case_id,
                domain_key=item.get("domain_key"),
                source_type="daily_log",
                source_id=daily_log.id,
                summary=label + (f" — {item.get('response_note')}" if item.get("response_note") else ""),
                visibility=item.get("visibility") or "INTERNAL_ONLY",
            )
        )

    for item in strategies:
        label = (item.get("strategy_label") or "").strip()
        if not label:
            continue
        db.add(
            StrategyUseEvent(
                daily_log_id=daily_log.id,
                strategy_id=item.get("strategy_id"),
                strategy_label=label,
                outcome_note=item.get("outcome_note"),
            )
        )

    if goal_labels:
        dual = daily_log.goals_addressed or ""
        merged = dual.strip()
        append = "; ".join(goal_labels)
        daily_log.goals_addressed = f"{merged}\n{append}".strip() if merged else append

    db.commit()
    return entries_for_log(db, daily_log.id)
