"""Clinical AI mock helpers — no LLM."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.models.user import User
from app.services import clinical_ai_service as ai_svc
from app.services import goal_repository_service as repo_svc

ensure_sqlite_schema_patches()


def test_classify_goal_domain_keyword():
    assert ai_svc.classify_goal_domain("Improve peer social skills at school") == "social_participation"


def test_rewrite_parent_summary_truncates():
    long_text = "word " * 100
    out = ai_svc.rewrite_parent_summary({"parent_notes": long_text})
    assert len(out) <= 280


def test_detect_duplicate_goal():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist
        label = "Unique duplicate detect goal xyz"
        repo_svc.create_goal_candidate(
            db,
            case_id=case.id,
            user_id=therapist.id,
            domain_key="communication",
            label=label,
        )
        hits = ai_svc.detect_duplicate_goal(db, label[:20], case.id)
        assert any(h["label"] == label for h in hits)
