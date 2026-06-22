"""Goal repository local candidates and CM approval."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.models.user import User
from app.services import goal_repository_service as repo_svc

ensure_sqlite_schema_patches()


def test_goal_repository_local_and_approve():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        admin = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and admin and therapist

        item = repo_svc.create_goal_candidate(
            db,
            case_id=case.id,
            user_id=therapist.id,
            domain_key="communication_aac",
            label="Child will request breaks using AAC",
            rationale="Observed in sessions",
        )
        assert item["status"] == "local"

        approved = repo_svc.approve_goal_candidate(db, item["id"], admin.id)
        assert approved["status"] == "approved"
        assert approved["case_id"] is None


def test_goal_repository_review_actions():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist
        item = repo_svc.create_goal_candidate(
            db,
            case_id=case.id,
            user_id=therapist.id,
            domain_key="peer_social",
            label="Child will initiate peer play with visual support",
        )
        reviewed = repo_svc.review_goal_item(
            db,
            item["id"],
            action="approve_case",
            actor_user_id=therapist.id,
        )
        assert reviewed["status"] == "active"
