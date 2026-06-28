"""Strategy suggestion API and rule engine."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.services import strategy_suggestion_service as sug_svc

ensure_sqlite_schema_patches()


def test_strategy_suggestions_returns_items():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        items = sug_svc.suggest_alternative_strategies(db, case_id=case.id, goal_card_id=None, limit=3)
        assert len(items) >= 1
        assert items[0]["label"]
