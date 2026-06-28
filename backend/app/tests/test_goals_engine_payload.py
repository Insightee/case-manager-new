"""Goals engine payload and admin repository list."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.models.user import User
from app.services import goal_repository_service as repo_svc
from app.services import goals_engine_service as engine_svc

ensure_sqlite_schema_patches()


def test_goals_engine_payload_shape():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist

        repo_svc.create_goal_candidate(
            db,
            case_id=case.id,
            user_id=therapist.id,
            domain_key="communication",
            label="Child will use AAC to request a break",
            core_domains=["communication"],
            core_environments=["school_classroom"],
            baseline_state="Needs adult prompt",
            desired_state="Independent request",
        )

        payload = engine_svc.build_goals_engine_payload(db, case.id)
        assert payload["case_id"] == case.id
        assert "iep_goals" in payload
        assert "goals" in payload
        assert "strategies" in payload
        assert payload["pending_count"] >= 1
        assert "filter_domains" in payload


def test_admin_goal_strategy_repository_lists_pending():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist

        repo_svc.create_strategy_candidate(
            db,
            case_id=case.id,
            user_id=therapist.id,
            label="Visual schedule for transitions",
            strategy_steps=["Show schedule", "Point to next", "Celebrate transition"],
            core_domains=["transitions"],
        )

        data = engine_svc.list_admin_goal_strategy_repository(db, limit=20)
        assert "pending_goals" in data
        assert "pending_strategies" in data
        assert any(s["label"] == "Visual schedule for transitions" for s in data["pending_strategies"])
