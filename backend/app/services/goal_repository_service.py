from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal_repository import GoalRepositoryItem, RepositoryItemStatus, StrategyRepositoryItem


def _goal_to_dict(row: GoalRepositoryItem) -> dict:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "domain_key": row.domain_key,
        "label": row.label,
        "rationale": row.rationale,
        "status": row.status,
        "created_by_user_id": row.created_by_user_id,
    }


def _strategy_to_dict(row: StrategyRepositoryItem) -> dict:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "label": row.label,
        "when_to_use": row.when_to_use,
        "how_to_use": row.how_to_use,
        "avoid": row.avoid,
        "status": row.status,
        "created_by_user_id": row.created_by_user_id,
    }


def list_goal_candidates(db: Session, case_id: int) -> list[dict]:
    rows = db.scalars(
        select(GoalRepositoryItem)
        .where(GoalRepositoryItem.case_id == case_id)
        .order_by(GoalRepositoryItem.id.desc())
    ).all()
    return [_goal_to_dict(r) for r in rows]


def create_goal_candidate(
    db: Session,
    *,
    case_id: int,
    user_id: int,
    domain_key: str,
    label: str,
    rationale: str | None = None,
) -> dict:
    row = GoalRepositoryItem(
        case_id=case_id,
        created_by_user_id=user_id,
        domain_key=domain_key,
        label=label.strip(),
        rationale=rationale,
        status=RepositoryItemStatus.LOCAL.value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _goal_to_dict(row)


def approve_goal_candidate(db: Session, item_id: int, approver_id: int) -> dict | None:
    row = db.get(GoalRepositoryItem, item_id)
    if not row:
        return None
    from datetime import datetime, timezone

    row.status = RepositoryItemStatus.APPROVED.value
    row.approved_by_user_id = approver_id
    row.approved_at = datetime.now(timezone.utc)
    if row.case_id is not None:
        row.case_id = None
    db.commit()
    db.refresh(row)
    return _goal_to_dict(row)


def list_strategy_candidates(db: Session, case_id: int) -> list[dict]:
    rows = db.scalars(
        select(StrategyRepositoryItem)
        .where(StrategyRepositoryItem.case_id == case_id)
        .order_by(StrategyRepositoryItem.id.desc())
    ).all()
    return [_strategy_to_dict(r) for r in rows]


def create_strategy_candidate(
    db: Session,
    *,
    case_id: int,
    user_id: int,
    label: str,
    when_to_use: str | None = None,
    how_to_use: str | None = None,
    avoid: str | None = None,
) -> dict:
    row = StrategyRepositoryItem(
        case_id=case_id,
        created_by_user_id=user_id,
        label=label.strip(),
        when_to_use=when_to_use,
        how_to_use=how_to_use,
        avoid=avoid,
        status=RepositoryItemStatus.LOCAL.value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)
