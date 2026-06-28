"""Ranked organisation strategy pool matches — deterministic, no AI."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.clinical_scoring import NEGATIVE_STRATEGY_FEEDBACK
from app.models.clinical_evidence import StrategyUseEvent
from app.models.daily_log import DailyLog
from app.models.goal_repository import RepositoryItemStatus, StrategyRepositoryItem
from app.models.session import Session as TherapySession
from app.services.clinical_brain_metadata import evidence_label_from_uses, parse_metadata
from app.services.strategy_repository_stats_service import aggregate_usage_for_strategy

_POOL_STATUSES = (
    RepositoryItemStatus.APPROVED.value,
    RepositoryItemStatus.ACTIVE.value,
)


def _rank_score(
    row: StrategyRepositoryItem,
    *,
    domain: str | None,
    support_need: str | None,
    environment: str | None,
    support_level: str | None,
    case_usage: int,
    total_usage: int,
    helpful_ratio: float,
) -> int:
    score = 0
    meta = parse_metadata(row.metadata_json)
    if domain and row.domain_key == domain:
        score += 3
    if support_need and meta.get("support_need") == support_need:
        score += 3
    envs = meta.get("environments") or []
    if environment and (row.environment_context == environment or environment in envs):
        score += 2
    if support_level and meta.get("support_level") == support_level:
        score += 2
    score += min(case_usage, 5)
    score += min(total_usage // 3, 3)
    if helpful_ratio >= 0.5:
        score += 2
    return score


def match_strategy_pool(
    db: Session,
    case_id: int,
    *,
    domain: str | None = None,
    support_need: str | None = None,
    environment: str | None = None,
    support_level: str | None = None,
    goal_card_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    del goal_card_id  # reserved for future goal-card domain join
    pool = db.scalars(
        select(StrategyRepositoryItem).where(
            StrategyRepositoryItem.case_id.is_(None),
            StrategyRepositoryItem.status.in_(_POOL_STATUSES),
        )
    ).all()

    log_ids = [
        lid
        for (lid,) in db.execute(
            select(DailyLog.id).join(TherapySession).where(TherapySession.case_id == case_id)
        ).all()
    ]
    case_counts: dict[int, int] = {}
    if log_ids:
        for sid, cnt in db.execute(
            select(StrategyUseEvent.strategy_id, func.count())
            .where(
                StrategyUseEvent.daily_log_id.in_(log_ids),
                StrategyUseEvent.strategy_id.isnot(None),
            )
            .group_by(StrategyUseEvent.strategy_id)
        ).all():
            if sid:
                case_counts[sid] = cnt

    ranked: list[tuple[int, StrategyRepositoryItem, dict]] = []
    for row in pool:
        usage = aggregate_usage_for_strategy(db, row.id)
        total = usage["usage_count"]
        helpful = usage.get("helpful_count") or 0
        ratio = helpful / total if total else 0
        score = _rank_score(
            row,
            domain=domain,
            support_need=support_need,
            environment=environment,
            support_level=support_level,
            case_usage=case_counts.get(row.id, 0),
            total_usage=total,
            helpful_ratio=ratio,
        )
        meta = parse_metadata(row.metadata_json)
        why = []
        if domain and row.domain_key == domain:
            why.append("domain match")
        if support_need and meta.get("support_need") == support_need:
            why.append("support need match")
        if environment and row.environment_context == environment:
            why.append("environment match")
        if case_counts.get(row.id):
            why.append("used on this case recently")
        ranked.append(
            (
                score,
                row,
                {
                    "usage_summary": f"{total} uses",
                    "why_matched": ", ".join(why) if why else "approved organisation strategy",
                    "evidence_label": evidence_label_from_uses(total),
                },
            )
        )

    ranked.sort(key=lambda t: (-t[0], t[1].id))
    out: list[dict] = []
    for _score, row, extra in ranked[:limit]:
        meta = parse_metadata(row.metadata_json)
        out.append(
            {
                "strategy_id": row.id,
                "id": row.id,
                "label": row.label,
                "title": row.label,
                "purpose": row.when_to_use or row.expected_outcome,
                "domain": row.domain_key,
                "domain_key": row.domain_key,
                "support_need": meta.get("support_need"),
                "environment_tags": meta.get("environments") or (
                    [row.environment_context] if row.environment_context else []
                ),
                "support_level_tags": [meta["support_level"]] if meta.get("support_level") else [],
                "caution": row.avoid,
                "parent_friendly_explanation": meta.get("parent_friendly_explanation"),
                **extra,
            }
        )
    return out
