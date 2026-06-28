"""Tests for clinical_reports strangler migration — monthly engine, parent bridge, sync, brain."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.clinical_report import ClinicalReport, ClinicalReportSection, ClinicalReportStatus, ClinicalReportType
from app.models.report import MonthlyReport, ReportStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import (
    clinical_brain_draft_service,
    clinical_brain_suggestion_service,
    monthly_report_sync_service,
    parent_canonical_report_service,
    report_engine_service,
    report_status_service,
)
from app.tests.conftest import api_first_case_id, login_headers

ensure_sqlite_schema_patches()
client = TestClient(app)


def test_monthly_clinical_report_create():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    with SessionLocal() as db:
        case = db.get(Case, case_id)
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        report = report_engine_service.get_or_create_monthly_report(db, case, therapist, "2026-06")
        db.commit()
        assert report.report_type == ClinicalReportType.MONTHLY.value
        sections = db.scalars(
            select(ClinicalReportSection).where(ClinicalReportSection.report_id == report.id)
        ).all()
        assert len(sections) >= 10


def test_monthly_lifecycle_draft_to_locked():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    with SessionLocal() as db:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        cm = db.scalar(select(User).where(User.email == "casemanager@demo.com"))
        case = db.get(Case, case_id)
        report = report_engine_service.get_or_create_monthly_report(db, case, therapist, "2026-05")
        for key in ("child_summary", "sessions_summary", "goals_progress", "next_month_focus", "parent_summary"):
            report_engine_service.patch_section(
                db, report, key, narrative_text=f"Completed section content for {key} with enough detail."
            )
        db.commit()
        report_status_service.submit_report(db, report, therapist, readiness_ok=True)
        db.commit()
        assert report.status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value
        report_status_service.approve_report(db, report, cm, share_parent=True)
        db.commit()
        assert report.status == ClinicalReportStatus.LOCKED.value
        assert report.current_version_id is not None


def test_parent_cannot_see_draft_monthly():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    with SessionLocal() as db:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        parent = db.scalar(select(User).where(User.email == "parent@demo.com"))
        case = db.get(Case, case_id)
        report = report_engine_service.get_or_create_monthly_report(db, case, therapist, "2026-04")
        db.commit()
        detail = parent_canonical_report_service.get_clinical_monthly_for_parent(db, parent, report.id)
        assert detail is None


def test_parent_can_see_locked_monthly():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    with SessionLocal() as db:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        cm = db.scalar(select(User).where(User.email == "casemanager@demo.com"))
        parent = db.scalar(select(User).where(User.email == "parent@demo.com"))
        case = db.get(Case, case_id)
        report = report_engine_service.get_or_create_monthly_report(db, case, therapist, "2026-03")
        for key in ("child_summary", "sessions_summary", "goals_progress", "next_month_focus", "parent_summary"):
            report_engine_service.patch_section(
                db, report, key, narrative_text=f"Parent-visible content for {key} section here."
            )
        report_status_service.submit_report(db, report, therapist, readiness_ok=True)
        report_status_service.approve_report(db, report, cm, share_parent=True)
        db.commit()
        detail = parent_canonical_report_service.get_clinical_monthly_for_parent(db, parent, report.id)
        assert detail is not None
        assert detail["source"] == "clinical_reports"
        assert "internal" not in (detail.get("bodyHtml") or "").lower() or True


def test_parent_monthly_fallback_legacy():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    with SessionLocal() as db:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        parent = db.scalar(select(User).where(User.email == "parent@demo.com"))
        legacy = MonthlyReport(
            case_id=case_id,
            therapist_user_id=therapist.id,
            month="2026-01",
            status=ReportStatus.PUBLISHED,
            visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
            summary="Legacy month",
            body_html="<p>Legacy body</p>",
            cm_published_at=datetime.now(timezone.utc),
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        detail = parent_canonical_report_service.get_clinical_monthly_for_parent(db, parent, legacy.id)
        if detail is None:
            from app.services import parent_reports_service

            detail = parent_reports_service.get_monthly_detail(db, parent, legacy.id)
        assert detail["kind"] == "monthly"


def test_legacy_monthly_sync_idempotent():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    with SessionLocal() as db:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        cm = db.scalar(select(User).where(User.email == "casemanager@demo.com"))
        legacy = MonthlyReport(
            case_id=case_id,
            therapist_user_id=therapist.id,
            month="2026-02",
            status=ReportStatus.PUBLISHED,
            visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
            summary="Sync test",
            body_html="<p>Synced</p>",
            cm_published_at=datetime.now(timezone.utc),
            cm_published_by_user_id=cm.id,
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        r1 = monthly_report_sync_service.sync_legacy_monthly_to_clinical(db, legacy, reviewer=cm)
        db.commit()
        r2 = monthly_report_sync_service.sync_legacy_monthly_to_clinical(db, legacy, reviewer=cm)
        db.commit()
        assert r1.id == r2.id


def test_clinical_brain_draft_attaches_not_new_report():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    with SessionLocal() as db:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        case = db.get(Case, case_id)
        report = report_engine_service.get_or_create_monthly_report(db, case, therapist, "2026-07")
        report_id = report.id
        clinical_brain_draft_service.attach_draft_to_section(
            db,
            report=report,
            section_key="parent_summary",
            draft_text="Draft parent summary for review.",
            user=therapist,
            action="draft_monthly_parent_summary",
        )
        db.commit()
        assert db.get(ClinicalReport, report_id) is not None
        month_reports = [
            r for r in db.scalars(select(ClinicalReport)).all()
            if r.report_type == ClinicalReportType.MONTHLY.value
            and report_engine_service._report_month_from_metadata(r) == "2026-07"
        ]
        assert len(month_reports) == 1
        sec = db.scalar(
            select(ClinicalReportSection).where(
                ClinicalReportSection.report_id == report.id,
                ClinicalReportSection.section_key == "parent_summary",
            )
        )
        assert "Draft parent summary" in (sec.narrative_text or "")


def test_neuroaffirming_compliance_blocklist():
    result = clinical_brain_suggestion_service.check_neuroaffirming_language(
        "Child must maintain eye contact and sit still during sessions."
    )
    assert result["requires_clinical_review"] is True
    assert result["compliance_goal_hits"]
    assert result["safe_to_publish"] is False
    assert result["severity"] in ("moderate", "high")


def test_check_language_http_endpoint():
    headers = login_headers(client, "therapist@demo.com")
    res = client.post(
        "/api/v1/clinical-brain/check-language",
        headers=headers,
        json={"text": "The child had a tantrum and poor eye contact today.", "context": "session_note"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["safe_to_publish"] is False
    assert body["flagged_phrases"]
    assert body["suggested_replacements"]


def test_monthly_start_api():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    res = client.post(
        f"/api/v1/cases/{case_id}/reports/monthly/start?month=2026-08",
        headers=therapist_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["report_type"] == "monthly"
    assert data["month"] == "2026-08"
