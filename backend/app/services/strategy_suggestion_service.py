"""Rule-based strategy suggestions — AI-ready, no LLM required."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.clinical_scoring import NEGATIVE_STRATEGY_FEEDBACK
from app.models.clinical_evidence import StrategyUseEvent
from app.models.daily_log import DailyLog
from app.models.goal_repository import RepositoryItemStatus, StrategyRepositoryItem
from app.models.session import Session as TherapySession

_POOL_STATUSES = (
    RepositoryItemStatus.APPROVED.value,
    RepositoryItemStatus.ACTIVE.value,
)

_FALLBACK_STRATEGIES = [
    {
        "label": "Visual schedule",
        "when_to_use": "Before transitions or new activities",
        "environment_context": "SCHOOL",
    },
    {
        "label": "First-then board",
        "when_to_use": "When sequencing tasks",
        "environment_context": "HOME",
    },
    {
        "label": "Sensory break",
        "when_to_use": "When regulation dips mid-activity",
        "environment_context": "CENTER",
    },
    {
        "label": "Co-regulation pause",
        "when_to_use": "When child needs connection before correction",
        "environment_context": "HOME",
    },
    {
        "label": "Choice of two options",
        "when_to_use": "To increase participation with low demand",
        "environment_context": "ONLINE",
    },
]


def _rank_score(row: StrategyRepositoryItem, *, domain_key: str | None, environment: str | None) -> int:
    score = 0
    if domain_key and row.domain_key == domain_key:
        score += 3
    if environment and row.environment_context == environment:
        score += 2
    elif environment and row.environment_context is None:
        score += 1
    if row.when_to_use:
        score += 1
    return score


def suggest_alternative_strategies(
    db: Session,
    *,
    case_id: int,
    goal_card_id: int | None = None,
    domain_key: str | None = None,
    environment: str | None = None,
    exclude_strategy_ids: list[int] | None = None,
    limit: int = 5,
) -> list[dict]:
    exclude = set(exclude_strategy_ids or [])
    negative_labels: set[str] = set()
    log_ids = [
        lid
        for (lid,) in db.execute(
            select(DailyLog.id)
            .join(TherapySession)
            .where(TherapySession.case_id == case_id)
        ).all()
    ]
    if log_ids:
        for ev in db.scalars(
            select(StrategyUseEvent).where(
                StrategyUseEvent.daily_log_id.in_(log_ids),
                StrategyUseEvent.strategy_feedback.in_(NEGATIVE_STRATEGY_FEEDBACK),
            )
        ).all():
            if ev.strategy_id:
                exclude.add(ev.strategy_id)
            if ev.strategy_label:
                negative_labels.add(ev.strategy_label.lower())

    pool = db.scalars(
        select(StrategyRepositoryItem).where(
            or_(
                StrategyRepositoryItem.case_id.is_(None),
                StrategyRepositoryItem.case_id == case_id,
            ),
            StrategyRepositoryItem.status.in_(_POOL_STATUSES),
        )
    ).all()

    candidates: list[tuple[int, StrategyRepositoryItem]] = []
    for row in pool:
        if row.id in exclude:
            continue
        if row.label.lower() in negative_labels:
            continue
        candidates.append((_rank_score(row, domain_key=domain_key, environment=environment), row))

    candidates.sort(key=lambda t: (-t[0], t[1].id))
    results: list[dict] = []
    for _score, row in candidates[:limit]:
        results.append(
            {
                "strategy_id": row.id,
                "label": row.label,
                "why_it_may_help": row.when_to_use or row.how_to_use or "Used successfully in similar contexts.",
                "environment_fit": row.environment_context or "Any setting",
            }
        )

    if len(results) < 3:
        for fb in _FALLBACK_STRATEGIES:
            if len(results) >= limit:
                break
            if fb["label"].lower() in negative_labels:
                continue
            if any(r["label"] == fb["label"] for r in results):
                continue
            results.append(
                {
                    "strategy_id": None,
                    "label": fb["label"],
                    "why_it_may_help": fb["when_to_use"],
                    "environment_fit": fb["environment_context"],
                }
            )
    return results[:limit]
