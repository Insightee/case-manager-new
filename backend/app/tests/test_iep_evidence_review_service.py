"""IEP evidence review deterministic suggestions."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.case import Case
from app.services import iep_evidence_review_service as iep_review_svc


def test_iep_evidence_review_returns_goal_evidence():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        result = iep_review_svc.build_iep_evidence_review(db, case_id=case.id)
        assert "goal_evidence" in result
        assert "review_period" in result


def test_iep_evidence_review_is_idempotent_for_draft_suggestions():
    from sqlalchemy import func

    from app.models.iep_review_suggestion import IepReviewSuggestion

    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        before = db.scalar(select(func.count()).select_from(IepReviewSuggestion))
        iep_review_svc.build_iep_evidence_review(db, case_id=case.id)
        mid = db.scalar(select(func.count()).select_from(IepReviewSuggestion))
        iep_review_svc.build_iep_evidence_review(db, case_id=case.id)
        after = db.scalar(select(func.count()).select_from(IepReviewSuggestion))
        assert mid >= before
        assert after == mid
