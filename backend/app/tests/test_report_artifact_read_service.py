"""Tests for report artifact triple-read helpers."""

from __future__ import annotations

from datetime import date

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.case import Case
from app.models.case_document import CaseDocument, CaseDocumentCategory, CaseDocumentStatus
from app.services import report_artifact_read_service as artifact_read

ensure_sqlite_schema_patches()


def test_document_report_type_maps_monthly():
    assert artifact_read.document_report_type(CaseDocumentCategory.CLIENT_MONTHLY_REPORT.value) == "monthly_report"
    assert artifact_read.document_report_type(CaseDocumentCategory.OBSERVATION_REPORT.value) == "observation_report"


def test_history_item_from_case_document_shape():
    with SessionLocal() as db:
        case = db.query(Case).first()
        assert case is not None
        from app.models.assignment import CaseAssignment

        assignment = db.query(CaseAssignment).filter(CaseAssignment.case_id == case.id).first()
        user_id = assignment.therapist_user_id if assignment else 1
        doc = CaseDocument(
            case_id=case.id,
            child_id=case.child_id,
            category=CaseDocumentCategory.CLIENT_MONTHLY_REPORT.value,
            title="March 2026 PDF",
            report_month="March 2026",
            status=CaseDocumentStatus.APPROVED.value,
            submitted_by_user_id=user_id,
        )
        db.add(doc)
        db.flush()
        item = artifact_read.history_item_from_case_document(db, case, doc)
        assert item["source"] == "uploaded_pdf"
        assert item["type"] == "monthly_report"
        assert item["case_document_id"] == doc.id
        db.rollback()


def test_dedupe_key_stable():
    key = artifact_read.dedupe_key(1, "monthly_report", "2026-03")
    assert key == (1, "monthly_report", "2026-03")
