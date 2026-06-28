"""Parent-safe monthly preview serializer."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.report import MonthlyReport
from app.services import parent_safe_report_serializer as parent_safe

ensure_sqlite_schema_patches()


def test_parent_safe_monthly_preview():
    with SessionLocal() as db:
        report = db.scalars(select(MonthlyReport).limit(1)).first()
        assert report
        out = parent_safe.serialize_parent_safe_monthly(db, report, case_code="TEST", child_name="Child")
        assert out["report_id"] == report.id
        assert "sections" in out
        assert "internal_cm_notes" not in str(out)
