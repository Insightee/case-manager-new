"""Therapist transition handover — dual assignment, billing deferred until completion."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CompensationMode
from app.models.case_therapist_transition import CaseTherapistTransition, CaseTherapistTransitionStatus
from app.seed.demo_seed import run as seed_run
from app.services import therapist_transition_service

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str = "superadmin@demo.com") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _pick_two_therapists(ah: dict[str, str]) -> tuple[int, int]:
    th = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=ah,
    )
    therapists = th.json() if isinstance(th.json(), list) else th.json().get("items", [])
    if len(therapists) < 2:
        pytest.skip("Need two therapists")
    t1 = therapists[0].get("therapist_user_id") or therapists[0].get("user_id")
    t2 = therapists[1].get("therapist_user_id") or therapists[1].get("user_id")
    if t1 == t2:
        pytest.skip("Need distinct therapists")
    return int(t1), int(t2)


def _prepare_case_with_therapist(case_id: int, therapist_id: int, ah: dict[str, str]) -> None:
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        case.billing_type = BillingType.PER_SESSION
        case.client_rate_per_session_inr = 1200
        case.compensation_mode = CompensationMode.PERCENTAGE
        case.pay_share_amount_inr = 600
        for a in db.scalars(select(CaseAssignment).where(CaseAssignment.case_id == case_id)).all():
            if a.status == CaseAssignmentStatus.ACTIVE:
                a.status = CaseAssignmentStatus.ENDED
                a.end_date = date(2026, 7, 1)
        db.commit()
    finally:
        db.close()

    res = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=ah,
        json={"therapist_user_id": therapist_id, "start_date": "2026-07-01"},
    )
    assert res.status_code == 201, res.text


def test_create_transition_adds_second_active_assignment():
    ah = _headers(_login())
    cases = client.get("/api/v1/cases?page_size=10", headers=ah)
    items = cases.json().get("items") or cases.json()
    if not items:
        pytest.skip("No cases")
    case_id = items[0]["id"]
    t1, t2 = _pick_two_therapists(ah)
    _prepare_case_with_therapist(case_id, t1, ah)

    start = date(2026, 9, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(3)]

    created = client.post(
        f"/api/v1/cases/{case_id}/transitions",
        headers=ah,
        json={
            "incoming_therapist_user_id": t2,
            "transition_dates": dates,
            "billing_update": {
                "billing_type": "PER_SESSION",
                "client_rate_per_session_inr": 1500,
                "compensation_mode": "PERCENTAGE",
                "pay_share_amount_inr": 800,
            },
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] in ("SCHEDULED", "ACTIVE")
    assert body["incoming_therapist_user_id"] == t2
    assert len(body["transition_dates"]) == 3

    assignments = client.get(f"/api/v1/cases/{case_id}/assignments", headers=ah)
    assert assignments.status_code == 200
    active = [a for a in assignments.json() if a["status"] == "ACTIVE"]
    assert len(active) == 2
    assert {a["therapist_user_id"] for a in active} == {t1, t2}

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert float(case.client_rate_per_session_inr) == 1200
    finally:
        db.close()


def test_reassignment_blocked_during_active_transition():
    ah = _headers(_login())
    cases = client.get("/api/v1/cases?page_size=10", headers=ah)
    items = cases.json().get("items") or cases.json()
    if not items:
        pytest.skip("No cases")
    case_id = items[0]["id"]
    t1, t2 = _pick_two_therapists(ah)
    _prepare_case_with_therapist(case_id, t1, ah)

    start = date(2026, 10, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(3)]
    created = client.post(
        f"/api/v1/cases/{case_id}/transitions",
        headers=ah,
        json={
            "incoming_therapist_user_id": t2,
            "transition_dates": dates,
            "billing_update": {
                "billing_type": "PER_SESSION",
                "client_rate_per_session_inr": 1500,
                "compensation_mode": "PERCENTAGE",
                "pay_share_amount_inr": 800,
            },
        },
    )
    assert created.status_code == 201, created.text

    blocked = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=ah,
        json={
            "therapist_user_id": t2,
            "start_date": "2026-10-05",
            "reason_for_change": "Attempt reassignment during transition",
        },
    )
    assert blocked.status_code == 400
    assert "transition" in blocked.json()["detail"].lower()


def test_transition_completes_and_applies_billing():
    ah = _headers(_login())
    cases = client.get("/api/v1/cases?page_size=10", headers=ah)
    items = cases.json().get("items") or cases.json()
    if not items:
        pytest.skip("No cases")
    case_id = items[0]["id"]
    t1, t2 = _pick_two_therapists(ah)
    _prepare_case_with_therapist(case_id, t1, ah)

    start = date(2026, 8, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(3)]

    created = client.post(
        f"/api/v1/cases/{case_id}/transitions",
        headers=ah,
        json={
            "incoming_therapist_user_id": t2,
            "transition_dates": dates,
            "billing_update": {
                "billing_type": "PER_SESSION",
                "client_rate_per_session_inr": 1800,
                "compensation_mode": "PERCENTAGE",
                "pay_share_amount_inr": 900,
            },
        },
    )
    assert created.status_code == 201, created.text
    transition_id = created.json()["id"]

    db = SessionLocal()
    try:
        transition = db.get(CaseTherapistTransition, transition_id)
        therapist_transition_service.complete_transition(db, transition, actor_user_id=1)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert float(case.client_rate_per_session_inr) == 1800
        assert float(case.pay_share_amount_inr) == 900
        transition = db.get(CaseTherapistTransition, transition_id)
        assert transition.status == CaseTherapistTransitionStatus.COMPLETED
        outgoing = db.get(CaseAssignment, transition.outgoing_assignment_id)
        assert outgoing.status == CaseAssignmentStatus.TRANSFERRED
        assert outgoing.end_date == date(2026, 8, 3)
    finally:
        db.close()

    timeline = client.get(f"/api/v1/admin/cases/{case_id}/timeline", headers=ah)
    assert timeline.status_code == 200
    labels = [i.get("action_label") or "" for i in timeline.json()["items"]]
    assert any("transition" in label.lower() for label in labels)
