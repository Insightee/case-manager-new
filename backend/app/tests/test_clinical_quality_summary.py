"""Clinical quality summary and workbench service."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.models.user import User
from app.services import clinical_workbench_service as wb_svc
from app.services import goal_repository_service as repo_svc

ensure_sqlite_schema_patches()


def test_clinical_quality_summary_shape():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        summary = wb_svc.build_clinical_quality_summary(db, case.id)
        assert summary["case_id"] == case.id
        assert summary["documentation_status"] in ("complete", "in_progress", "needs_revision")
        assert summary["risk_level"] in ("ok", "attention", "urgent")
        assert "recommended_next_actions" in summary
        assert "evidence_summary" in summary


def test_reports_workbench_delegates():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist
        wb = wb_svc.build_reports_workbench(db, case, therapist)
        assert wb["case_id"] == case.id
        assert "observation" in wb
        assert "monthly_reports" in wb


def test_pending_goal_candidate_in_summary():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist
        repo_svc.create_goal_candidate(
            db,
            case_id=case.id,
            user_id=therapist.id,
            domain_key="communication_aac",
            label="Test pending goal for quality summary",
            rationale="test",
        )
        db.commit()
        summary = wb_svc.build_clinical_quality_summary(db, case.id)
        assert "custom_items_pending_review" in summary["missing_items"] or summary["custom_items_pending_review"]["goals"]
