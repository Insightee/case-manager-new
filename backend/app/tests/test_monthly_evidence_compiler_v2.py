"""Monthly evidence compiler v2."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.report import MonthlyReport, ReportStatus
from app.models.user import User
from app.services import monthly_report_evidence_compiler as compiler

ensure_sqlite_schema_patches()


def test_compile_evidence_v2_draft():
    with SessionLocal() as db:
        report = db.scalars(
            select(MonthlyReport).where(MonthlyReport.status == ReportStatus.DRAFT).limit(1)
        ).first()
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        if not report or not user:
            return
        out = compiler.compile_evidence_v2(db, user, report)
        assert out["body_html_updated"] is True
        assert "sections" in out
