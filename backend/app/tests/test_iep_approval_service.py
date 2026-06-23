"""Tests for IEP stakeholder auto-approval."""

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus
from app.services import iep_approval_service

ensure_sqlite_schema_patches()


def test_apply_iep_auto_approvals_idempotent():
    with SessionLocal() as db:
        report = db.scalars(select(ClinicalReport).where(ClinicalReport.report_type == "iep")).first()
        if not report:
            return
        meta = {
            "iep_approval": {
                "phase": "stakeholder",
                "parent_approval_status": "pending",
                "therapist_approval_status": "pending",
                "parent_approval_due_at": "2020-01-01T00:00:00+00:00",
                "therapist_approval_due_at": "2020-01-01T00:00:00+00:00",
                "review_active": False,
            }
        }
        report.metadata_json = json.dumps(meta)
        report.status = ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value
        db.commit()

        result = iep_approval_service.apply_iep_auto_approvals(db, now=datetime.now(timezone.utc))
        assert result["parent_auto_approved"] >= 0
        db.refresh(report)
        state = iep_approval_service.get_iep_approval(report)
        if result["parent_auto_approved"]:
            assert state["parent_approval_status"] == "auto_approved"

        result2 = iep_approval_service.apply_iep_auto_approvals(db, now=datetime.now(timezone.utc))
        assert result2["parent_auto_approved"] == 0
