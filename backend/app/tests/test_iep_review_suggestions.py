"""IEP review suggestions — draft only, no active IEP mutation."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.services import iep_review_suggestions_service as svc

ensure_sqlite_schema_patches()


def test_list_iep_review_suggestions():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        out = svc.list_suggestions(db, case.id)
        assert "items" in out
