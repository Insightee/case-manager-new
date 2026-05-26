from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.report import MonthlyReport, ReportStatus
from app.models.visibility import VisibilityStatus
from app.seed.demo_seed import run as seed_run
from app.services import report_service
from app.tests.conftest import api_items

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _under_review_monthly_id(headers: dict) -> int | None:
    reports = client.get("/api/v1/reports/monthly", headers=headers, params={"status": "UNDER_REVIEW"})
    assert reports.status_code == 200
    items = api_items(reports.json())
    return items[0]["id"] if items else None


def test_parent_cannot_see_without_cm_publish():
    from app.core.database import SessionLocal
    from app.services.parent_reports_service import parent_can_see_monthly

    db = SessionLocal()
    try:
        report = db.query(MonthlyReport).filter(MonthlyReport.status == ReportStatus.UNDER_REVIEW).first()
        if not report:
            pytest.skip("no under review report")
        report.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
        report.cm_published_at = None
        report.admin_published_at = None
        assert parent_can_see_monthly(report) is False
    finally:
        db.close()


def test_admin_override_blocked_before_10_days():
    headers = _login("superadmin@demo.com")
    rid = _under_review_monthly_id(headers)
    if not rid:
        pytest.skip("no under review report")
    res = client.post(
        f"/api/v1/admin/reports/monthly/{rid}/publish-to-parent",
        headers=headers,
        json={"comment": "Early override"},
    )
    assert res.status_code == 400


def test_cm_publish_makes_parent_visible():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        for report in db.query(MonthlyReport).all():
            report.admin_published_at = None
            report.cm_published_at = None
            report.status = ReportStatus.UNDER_REVIEW
        db.commit()
    finally:
        db.close()

    cm_headers = _login("shadowcm@demo.com")
    rid = _under_review_monthly_id(cm_headers)
    if not rid:
        pytest.skip("no under review report")
    pub = client.post(
        f"/api/v1/admin/reports/monthly/{rid}/publish-to-parent",
        headers=cm_headers,
        json={"comment": "Ready for parents"},
    )
    assert pub.status_code == 200
    detail = pub.json()
    assert detail.get("cm_published_at") or detail.get("status") == "PUBLISHED"

    parent_headers = _login("parent@demo.com")
    parent_list = client.get("/api/v1/parent/reports", headers=parent_headers)
    assert parent_list.status_code == 200
    ids = {str(x.get("id")) for x in api_items(parent_list.json())}
    assert str(rid) in ids

    db = SessionLocal()
    try:
        report = db.get(MonthlyReport, rid)
        report.submitted_for_review_at = datetime.now(timezone.utc) - timedelta(days=11)
        report.cm_published_at = None
        report.admin_published_at = None
        report.status = ReportStatus.UNDER_REVIEW
        db.commit()
    finally:
        db.close()

    admin_headers = _login("superadmin@demo.com")
    override = client.post(
        f"/api/v1/admin/reports/monthly/{rid}/publish-to-parent",
        headers=admin_headers,
        json={"comment": "Override"},
    )
    assert override.status_code == 200


def test_send_for_review_requires_comment():
    headers = _login("superadmin@demo.com")
    rid = _under_review_monthly_id(headers)
    if not rid:
        pytest.skip("no under review report")
    bad = client.post(
        f"/api/v1/admin/reports/monthly/{rid}/send-for-review",
        headers=headers,
        json={"target": "therapist", "comment": "   "},
    )
    assert bad.status_code == 400


def test_admin_hub_excludes_incident_category():
    headers = _login("superadmin@demo.com")
    res = client.get("/api/v1/admin/reports/monthly", headers=headers, params={"category": "INCIDENT_DOCUMENT"})
    assert res.status_code == 200
    assert len(api_items(res.json())) == 0


def test_monthly_detail_includes_summary_when_body_empty():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        report = (
            db.query(MonthlyReport)
            .filter(MonthlyReport.summary.isnot(None), MonthlyReport.body_html.is_(None))
            .first()
        )
        if not report:
            report = db.query(MonthlyReport).first()
        if not report:
            pytest.skip("no reports")
        report.body_html = None
        report.summary = "Plain summary for parents"
        db.commit()
        rid = report.id
    finally:
        db.close()
    headers = _login("superadmin@demo.com")
    detail = client.get(f"/api/v1/admin/reports/monthly/{rid}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body.get("summary") == "Plain summary for parents"


def test_can_admin_override_publish_helper():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        report = db.query(MonthlyReport).first()
        assert report is not None
        report.submitted_for_review_at = datetime.now(timezone.utc) - timedelta(days=11)
        report.cm_published_at = None
        report.admin_published_at = None
        report.status = ReportStatus.UNDER_REVIEW
        assert report_service.can_admin_override_publish(report) is True
        report.submitted_for_review_at = datetime.now(timezone.utc)
        assert report_service.can_admin_override_publish(report) is False
    finally:
        db.close()
