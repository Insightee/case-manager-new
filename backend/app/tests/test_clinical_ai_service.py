"""Clinical AI service foundation."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User
from app.services import clinical_ai_service as ai_svc


def test_ai_disabled_returns_safe_payload():
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert user
        out = ai_svc.improve_session_note(db, user, raw_note="Child engaged well today", context={})
        assert out["status"] == "skipped"
        assert "message" in out


def test_parent_safe_language_check():
    result = ai_svc.check_parent_safe_language("Aarav participated with support today.")
    assert "is_parent_safe" in result
