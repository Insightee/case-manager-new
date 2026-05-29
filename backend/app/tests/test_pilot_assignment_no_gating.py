"""Pilot: assignment acceptance is informational; ACTIVE admin-assigned cases are fully usable."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.seed.demo_seed import run as seed_run
from app.services import assignment_acceptance_service as accept_svc
from sqlalchemy import select

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    assert settings.acceptance_gating_enabled is False
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mark_offer_sent_no_parent_accept(case_id: int) -> CaseAssignment:
    db = SessionLocal()
    try:
        assignment = db.scalars(
            select(CaseAssignment)
            .where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
            .order_by(CaseAssignment.id.desc())
        ).first()
        assert assignment is not None
        case = db.get(Case, case_id)
        case.status = CaseStatus.ACTIVE
        now = datetime.now(timezone.utc)
        assignment.assignment_offer_sent_at = now
        assignment.parent_accepted_at = None
        assignment.therapist_accepted_at = None
        db.commit()
        db.refresh(assignment)
        return assignment
    finally:
        db.close()


def _parent_case_id() -> int:
    token = _login("parent@demo.com")
    rows = client.get("/api/v1/parent/cases", headers=_headers(token)).json()
    assert rows, "seed should link parent@demo.com to at least one case"
    return int(rows[0]["id"])


def test_pilot_policy_helpers_do_not_gate():
    assert accept_svc.acceptance_gating_enabled() is False
    assert accept_svc.parent_has_accepted(None) is True
    assert accept_svc.therapist_may_operate_sessions(None) is True


def test_parent_case_detail_allowed_without_acceptance():
    case_id = _parent_case_id()
    _mark_offer_sent_no_parent_accept(case_id)
    token = _login("parent@demo.com")
    r = client.get(f"/api/v1/parent/cases/{case_id}", headers=_headers(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("caseId") or body.get("id")


def test_parent_iep_allowed_without_acceptance():
    case_id = _parent_case_id()
    _mark_offer_sent_no_parent_accept(case_id)
    token = _login("parent@demo.com")
    r = client.get(f"/api/v1/parent/cases/{case_id}/iep-plan", headers=_headers(token))
    assert r.status_code in (200, 404), r.text


def test_therapist_can_start_session_without_parent_acceptance():
    case_id = _parent_case_id()
    assignment = _mark_offer_sent_no_parent_accept(case_id)
    db = SessionLocal()
    try:
        session = db.scalars(
            select(TherapySession)
            .where(
                TherapySession.case_id == case_id,
                TherapySession.therapist_user_id == assignment.therapist_user_id,
                TherapySession.status == SessionStatus.SCHEDULED,
            )
            .order_by(TherapySession.scheduled_date.asc())
        ).first()
        if not session:
            pytest.skip("No scheduled session on parent demo case for therapist start test")
        sid = session.id
    finally:
        db.close()

    token = _login("therapist@demo.com")
    if assignment.therapist_user_id:
        from app.core.database import SessionLocal as SL
        from app.models.user import User

        db2 = SL()
        try:
            therapist = db2.get(User, assignment.therapist_user_id)
            if therapist and therapist.email != "therapist@demo.com":
                token = _login(therapist.email)
        finally:
            db2.close()

    start = client.post(f"/api/v1/sessions/{sid}/start", headers=_headers(token))
    assert start.status_code == 200, start.text
    assert start.json()["status"] == "IN_PROGRESS"
    client.post(f"/api/v1/sessions/{sid}/end", headers=_headers(token))


def test_activate_allotment_sets_active_and_offer_sent_without_parent_accept():
    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=ah,
    ).json()
    therapist_id = therapists[0]["therapist_user_id"]
    fam = client.post(
        "/api/v1/admin/families",
        headers=ah,
        json={
            "parent_email": f"pilot-parent-{suffix}@demo.com",
            "parent_full_name": "Pilot Parent",
            "child": {"first_name": "Pilot", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]
    allot = client.post(
        "/api/v1/admin/cases/allot",
        headers=_headers(_login("casemanager@demo.com")),
        json={
            "child_id": child_id,
            "service_type": "Homecare",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_pct": 60,
            "therapist_user_id": therapist_id,
        },
    )
    assert allot.status_code == 201, allot.text
    assert allot.json()["case"]["status"] == "PENDING_ALLOTMENT"
    case_id = allot.json()["case"]["id"]
    activate = client.post(f"/api/v1/admin/cases/{case_id}/activate-allotment", headers=ah)
    assert activate.status_code == 200, activate.text
    assert activate.json()["case"]["status"] == "ACTIVE"

    db = SessionLocal()
    try:
        assignment = db.scalars(
            select(CaseAssignment)
            .where(CaseAssignment.case_id == case_id, CaseAssignment.status == CaseAssignmentStatus.ACTIVE)
        ).first()
        assert assignment is not None
        assert assignment.assignment_offer_sent_at is not None
        assert assignment.parent_accepted_at is None
    finally:
        db.close()

    admin_case = client.get(f"/api/v1/cases/{case_id}", headers=ah)
    assert admin_case.status_code == 200, admin_case.text


def test_parent_accept_sets_timestamp_when_offer_sent():
    case_id = _parent_case_id()
    assignment = _mark_offer_sent_no_parent_accept(case_id)
    token = _login("parent@demo.com")
    r = client.post(
        f"/api/v1/parent/assignments/{assignment.id}/accept",
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        refreshed = db.get(CaseAssignment, assignment.id)
        assert refreshed.parent_accepted_at is not None
    finally:
        db.close()
