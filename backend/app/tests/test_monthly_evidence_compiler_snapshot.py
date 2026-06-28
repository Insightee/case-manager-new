"""Monthly evidence compiler snapshot."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.case import Case
from app.models.user import User
from app.services import monthly_evidence_compiler_service as compiler_svc


def test_compiler_returns_structured_payload():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        month = "2099-06"
        payload = compiler_svc.compile_monthly_evidence_snapshot(
            db, case_id=case.id, month=month, user_id=1, force=True
        )
        assert payload["case_id"] == case.id
        assert payload["month"] == month
        assert "sessions" in payload
        assert "goals" in payload
        assert "quality_flags" in payload
        assert payload.get("source_hash")


def test_get_latest_snapshot_after_compile():
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        month = "2099-07"
        compiler_svc.compile_monthly_evidence_snapshot(db, case_id=case.id, month=month, force=True)
        snap = compiler_svc.get_latest_snapshot(db, case.id, month)
        assert snap is not None
        assert snap["month"] == month
