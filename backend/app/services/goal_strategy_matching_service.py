"""Layer 1–3 duplicate strategy search before observation candidate create."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal_repository import StrategyRepositoryItem


def find_matching_strategies(db: Session, label: str, *, case_id: int | None = None, limit: int = 5) -> list[dict]:
    q = label.strip()
    if len(q) < 2:
        return []
    stmt = select(StrategyRepositoryItem).where(StrategyRepositoryItem.label.ilike(f"%{q}%"))
    if case_id:
        stmt = stmt.where(
            (StrategyRepositoryItem.case_id == case_id) | (StrategyRepositoryItem.scope == "org")
        )
    rows = list(db.scalars(stmt.limit(limit)).all())
    return [
        {
            "id": r.id,
            "label": r.label,
            "status": r.status,
            "how_to_use": r.how_to_use,
            "scope": r.scope,
        }
        for r in rows
    ]
