"""Deterministic strategy use stats rollup — no AI."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal_repository import StrategyRepositoryStats
from app.services.clinical_brain_metadata import evidence_label_from_uses


FEEDBACK_COUNTERS = {
    "HELPFUL": "helpful_count",
    "PARTLY_HELPFUL": "partly_helpful_count",
    "NOT_HELPFUL": "not_helpful_count",
    "CHILD_REJECTED": "child_rejected_count",
    "NEEDS_ADAPTATION": "needs_adaptation_count",
}


def _compute_evidence_strength(total: int, helpful: int) -> str:
    if total < 3:
        return "weak"
    ratio = helpful / total if total else 0
    if total >= 10 and ratio >= 0.5:
        return "emerging_strong"
    return "moderate"


def record_strategy_use(
    db: Session,
    *,
    strategy_repository_item_id: int | None,
    goal_domain: str | None = None,
    support_need: str | None = None,
    environment_context: str | None = None,
    support_level_tier: str | None = None,
    strategy_feedback: str | None = None,
    used_as_adapted: bool = False,
    commit: bool = False,
) -> None:
    if not strategy_repository_item_id:
        return
    row = db.scalar(
        select(StrategyRepositoryStats).where(
            StrategyRepositoryStats.strategy_repository_item_id == strategy_repository_item_id,
            StrategyRepositoryStats.goal_domain == goal_domain,
            StrategyRepositoryStats.support_need == support_need,
            StrategyRepositoryStats.environment_context == environment_context,
            StrategyRepositoryStats.support_level_tier == support_level_tier,
        )
    )
    if not row:
        row = StrategyRepositoryStats(
            strategy_repository_item_id=strategy_repository_item_id,
            goal_domain=goal_domain,
            support_need=support_need,
            environment_context=environment_context,
            support_level_tier=support_level_tier,
        )
        db.add(row)
    row.total_uses = (row.total_uses or 0) + 1
    row.last_used_at = datetime.now(timezone.utc)
    fb = (strategy_feedback or "").upper()
    counter = FEEDBACK_COUNTERS.get(fb)
    if counter:
        setattr(row, counter, (getattr(row, counter) or 0) + 1)
    if used_as_adapted:
        row.adapted_count = (row.adapted_count or 0) + 1
    row.evidence_strength = _compute_evidence_strength(row.total_uses, row.helpful_count or 0)
    if commit:
        db.commit()
    else:
        db.flush()


def aggregate_usage_for_strategy(db: Session, strategy_id: int) -> dict:
    rows = db.scalars(
        select(StrategyRepositoryStats).where(StrategyRepositoryStats.strategy_repository_item_id == strategy_id)
    ).all()
    total = sum(r.total_uses or 0 for r in rows)
    helpful = sum(r.helpful_count or 0 for r in rows)
    strength = rows[0].evidence_strength if rows else None
    return {
        "usage_count": total,
        "evidence_strength": strength,
        "evidence_label": evidence_label_from_uses(total),
        "helpful_count": helpful,
    }
