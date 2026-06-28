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

        cm_item = repo_svc.create_goal_candidate(
            db,
            case_id=case.id,
            user_id=therapist.id,
            domain_key="peer_social",
            label="Child will co-regulate before group work",
            goal_use="cm_iep_review",
        )
        assert cm_item["status"] == "candidate"
        assert cm_item["lifecycle_status"] == "pending_review"
        assert cm_item["source"] == "cm_iep_review"

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


def test_goal_candidate_patch_submit_no_duplicate():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist
        item = repo_svc.create_goal_candidate(
            db,
            case_id=case.id,
            user_id=therapist.id,
            domain_key="communication",
            label="Child will use visual schedule for transitions",
            goal_statement="Child will follow visual schedule with support",
        )
        assert item["status"] == "local"
        before_id = item["id"]
        updated = repo_svc.update_goal_candidate(
            db,
            before_id,
            case_id=case.id,
            action="submit_for_cm_review",
        )
        assert updated
        assert updated["id"] == before_id
        assert updated["status"] == "candidate"
        assert updated["lifecycle_status"] == "pending_review"
