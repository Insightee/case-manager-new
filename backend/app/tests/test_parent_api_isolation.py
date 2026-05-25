"""Regression tests: parent APIs must not leak other families' data or staff-only fields."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.parent import ParentGuardian
from app.models.report import MonthlyReport, ParentReviewStatus, ReportStatus
from app.models.session import Session as TherapySession
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.seed.demo_seed import get_or_create_user, run as seed_run
from app.core.permissions import RoleName

client = TestClient(app)

FORBIDDEN_PARENT_KEYS = frozenset({
    "session_notes",
    "observations",
    "internal_notes",
    "reviewer_comment",
    "reviewerComment",
    "approval_status",
    "visibility_status",
    "therapist_user_id",
    "case_manager_user_id",
    "billing_type",
    "client_rate_per_session_inr",
    "pay_share_pct",
    "compensation_mode",
    "late_reason",
    "editable_until",
    "can_edit",
    "late_addition",
})


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str = "demo123") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _assert_no_forbidden_keys(payload: Any, *, path: str = "root") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert key not in FORBIDDEN_PARENT_KEYS, f"Forbidden key {path}.{key}"
            _assert_no_forbidden_keys(value, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for idx, item in enumerate(payload):
            _assert_no_forbidden_keys(item, path=f"{path}[{idx}]")


def _parent_case_id(headers: dict[str, str]) -> int:
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    assert cases, "Seed should include at least one parent case"
    return cases[0]["id"]


def test_parent_cannot_see_unapproved_daily_log():
    headers = _login("parent@demo.com")
    case_id = _parent_case_id(headers)

    db = SessionLocal()
    try:
        pending = db.scalars(
            select(DailyLog)
            .join(TherapySession)
            .where(
                TherapySession.case_id == case_id,
                DailyLog.approval_status == LogApprovalStatus.PENDING,
            )
        ).first()
        assert pending is not None, "Seed includes a pending-review daily log"
        pending_id = pending.id
        pending.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
        db.commit()
    finally:
        db.close()

    logs = client.get("/api/v1/parent/session-logs", headers=headers).json()
    assert all(row["id"] != pending_id for row in logs)

    home = client.get("/api/v1/parent/home", headers=headers).json()
    recent_ids = {u["id"] for u in home.get("recent_updates", [])}
    assert pending_id not in recent_ids
    for case in home.get("cases", []):
        highlight = case.get("session_highlight")
        if highlight:
            _assert_no_forbidden_keys(highlight, path="session_highlight")

    detail = client.get(f"/api/v1/parent/session-logs", headers=headers, params={"case_id": case_id})
    assert detail.status_code == 200
    assert all(row["id"] != pending_id for row in detail.json())

    feedback = client.patch(
        f"/api/v1/parent/session-logs/{pending_id}/feedback",
        headers=headers,
        json={"rating": 5},
    )
    assert feedback.status_code in (400, 404)


def test_parent_cannot_see_rejected_report():
    headers = _login("parent@demo.com")
    case_id = _parent_case_id(headers)

    db = SessionLocal()
    try:
        therapist_id = db.scalars(
            select(MonthlyReport.therapist_user_id).where(MonthlyReport.case_id == case_id).limit(1)
        ).first()
        if not therapist_id:
            therapist_id = get_or_create_user(
                db, "therapist@demo.com", "demo123", "Therapist", RoleName.THERAPIST.value
            ).id
        rejected = MonthlyReport(
            case_id=case_id,
            therapist_user_id=therapist_id,
            month="Rejected QA",
            status=ReportStatus.REJECTED,
            summary="Should not appear to parent",
            visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
            parent_review_status=ParentReviewStatus.PENDING.value,
            reviewer_comment="Internal rejection — staff only",
        )
        db.add(rejected)
        db.commit()
        rejected_id = rejected.id
    finally:
        db.close()

    hub = client.get("/api/v1/parent/reports/hub", headers=headers).json()
    hub_ids = {str(m["id"]) for m in hub.get("monthly", [])}
    assert str(rejected_id) not in hub_ids

    legacy = client.get("/api/v1/parent/reports", headers=headers).json()
    assert all(str(r.get("id")) != str(rejected_id) for r in legacy)

    detail = client.get(f"/api/v1/parent/reports/monthly/{rejected_id}", headers=headers)
    assert detail.status_code == 404

    detail_legacy = client.get(f"/api/v1/parent/reports/{rejected_id}", headers=headers)
    assert detail_legacy.status_code == 404


def test_parent_cannot_see_internal_notes():
    """Staff reviewer_comment and therapist session_notes must not appear in parent DTOs."""
    headers = _login("parent@demo.com")
    case_id = _parent_case_id(headers)

    db = SessionLocal()
    try:
        therapist_id = db.scalars(
            select(MonthlyReport.therapist_user_id).where(MonthlyReport.case_id == case_id).limit(1)
        ).first()
        if not therapist_id:
            therapist_id = get_or_create_user(
                db, "therapist@demo.com", "demo123", "Therapist", RoleName.THERAPIST.value
            ).id
        report = MonthlyReport(
            case_id=case_id,
            therapist_user_id=therapist_id,
            month="Published QA internal",
            status=ReportStatus.PUBLISHED,
            summary="Parent-visible summary",
            body_html="<p>Parent body</p>",
            visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
            parent_review_status=ParentReviewStatus.APPROVED.value,
            reviewer_comment="INTERNAL_STAFF_NOTE_XYZ",
        )
        db.add(report)
        db.commit()
        report_id = report.id
    finally:
        db.close()

    detail = client.get(f"/api/v1/parent/reports/monthly/{report_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert "reviewer_comment" not in body
    assert "INTERNAL_STAFF_NOTE_XYZ" not in json.dumps(body)

    logs = client.get("/api/v1/parent/session-logs", headers=headers).json()
    for row in logs:
        assert "session_notes" not in row
        assert "observations" not in row
        assert "internal_notes" not in row
        if row.get("parent_notes"):
            assert "Internal:" not in (row.get("headline") or "")


def test_parent_cannot_see_another_parents_child_or_case():
    db = SessionLocal()
    try:
        other = get_or_create_user(
            db,
            "parent-other@demo.com",
            "demo123",
            "Other Parent",
            RoleName.PARENT.value,
        )
        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == other.id)).first()
        if not pg:
            pg = ParentGuardian(user_id=other.id)
            db.add(pg)
            db.flush()
        db.commit()
        other_user_id = other.id
    finally:
        db.close()

    primary_headers = _login("parent@demo.com")
    other_headers = _login("parent-other@demo.com")
    primary_case_id = _parent_case_id(primary_headers)

    other_cases = client.get("/api/v1/parent/cases", headers=other_headers).json()
    other_case_ids = {c["id"] for c in other_cases}
    assert primary_case_id not in other_case_ids

    assert client.get(f"/api/v1/parent/cases/{primary_case_id}", headers=other_headers).status_code == 404
    assert (
        client.get(
            "/api/v1/parent/session-logs",
            headers=other_headers,
            params={"case_id": primary_case_id},
        ).status_code
        == 404
    )

    primary_reports = client.get("/api/v1/parent/reports/hub", headers=primary_headers).json()
    if primary_reports.get("monthly"):
        rid = primary_reports["monthly"][0]["id"]
        assert client.get(f"/api/v1/parent/reports/monthly/{rid}", headers=other_headers).status_code == 404

    db = SessionLocal()
    try:
        parent1 = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        n1 = client.get("/api/v1/parent/notifications", headers=primary_headers).json()
        if n1:
            nid = n1[0]["id"]
            assert (
                client.patch(
                    f"/api/v1/parent/notifications/{nid}/read",
                    headers=other_headers,
                ).status_code
                == 404
            )
        assert parent1 is not None
    finally:
        db.close()


def test_parent_home_does_not_leak_staff_fields():
    headers = _login("parent@demo.com")
    home = client.get("/api/v1/parent/home", headers=headers)
    assert home.status_code == 200
    data = home.json()
    _assert_no_forbidden_keys(data)

    assert "cases" in data
    for case in data["cases"]:
        allowed = {
            "id",
            "caseId",
            "childName",
            "serviceType",
            "productModule",
            "status",
            "therapistName",
            "caseManagerName",
            "latestApprovedReportMonth",
            "iepStatus",
            "upcomingBooking",
            "session_highlight",
        }
        assert set(case.keys()).issubset(allowed), f"Unexpected case keys: {set(case.keys()) - allowed}"
        if case.get("session_highlight"):
            highlight_allowed = {
                "headline",
                "summary_paragraph",
                "attendance_label",
                "what_we_did",
                "what_is_next",
                "scheduled_date",
                "therapist_name",
            }
            assert set(case["session_highlight"].keys()).issubset(highlight_allowed)

    notifications = client.get("/api/v1/parent/notifications", headers=headers)
    assert notifications.status_code == 200
    _assert_no_forbidden_keys(notifications.json())
