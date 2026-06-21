"""Mock AI provider — explicit preview only, no publish side effects."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.models.user import User
from app.services.ai_gateway_service import AIGatewayService
from app.services.ai_prompt_registry import ALLOWED_ACTIONS

ensure_sqlite_schema_patches()


def test_ai_mock_provider_preview():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and user

        out = AIGatewayService.preview(
            db,
            user_id=user.id,
            case_id=case.id,
            action="monthly_summary",
            context={"child_name": "Demo Child"},
        )
        assert out["draft_text"]
        assert out["log_id"]
        assert not out.get("cached")

        cached = AIGatewayService.preview(
            db,
            user_id=user.id,
            case_id=case.id,
            action="monthly_summary",
            context={"child_name": "Demo Child"},
        )
        assert cached.get("cached") is True


def test_expanded_ai_actions():
    assert "strategy_suggest" in ALLOWED_ACTIONS
    assert "clinical_review_note" in ALLOWED_ACTIONS

    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and user
        out = AIGatewayService.preview(
            db,
            user_id=user.id,
            case_id=case.id,
            action="strategy_suggest",
            context={"child_name": case.child_name if hasattr(case, "child_name") else "Demo", "domain_key": "communication_aac"},
        )
        assert out["draft_text"]
