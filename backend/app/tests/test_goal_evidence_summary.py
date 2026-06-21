"""Goal and strategy evidence summary aggregation."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.services import goal_evidence_aggregation_service as ev_agg

ensure_sqlite_schema_patches()


def test_goals_evidence_summary_weak_by_default():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        out = ev_agg.build_goals_evidence_summary(db, case.id)
        assert out["case_id"] == case.id
        assert "goals" in out


def test_strategies_evidence_summary_shape():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        out = ev_agg.build_strategies_evidence_summary(db, case.id)
        assert out["case_id"] == case.id
        assert "strategies" in out
