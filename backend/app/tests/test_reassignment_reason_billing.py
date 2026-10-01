"""Reassignment reason validation and billing snapshot on transfer."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CompensationMode
from app.services.assignment_service import validate_reassignment_reason
from app.services.reports_export_helpers import billing_snapshot_report_columns
from app.seed.demo_seed import run as seed_run

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


def test_validate_reassignment_reason_min_length():
    with pytest.raises(ValueError, match="at least 5"):
        validate_reassignment_reason("ab")
    assert validate_reassignment_reason("Caseload rebalance") == "Caseload rebalance"


def test_reassignment_requires_reason_and_snapshots_billing():
    ah = _headers(_login())
    cases = client.get("/api/v1/cases?page_size=10", headers=ah)
    items = cases.json().get("items") or cases.json()
    if not items:
        pytest.skip("No cases")
    case_id = items[0]["id"]

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

    first = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=ah,
        json={"therapist_user_id": t1, "start_date": "2026-07-01"},
    )
    assert first.status_code == 201, first.text

    bad = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=ah,
        json={"therapist_user_id": t2, "start_date": "2026-08-01", "reason_for_change": "no"},
    )
    assert bad.status_code == 400

    good = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=ah,
        json={
            "therapist_user_id": t2,
            "start_date": "2026-08-01",
            "reason_for_change": "Therapist relocated to another city",
        },
    )
    assert good.status_code == 201, good.text

    db = SessionLocal()
    try:
        transferred = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.therapist_user_id == t1,
                CaseAssignment.status == CaseAssignmentStatus.TRANSFERRED,
            )
        ).all()
        assert transferred
        snap = transferred[0].billing_snapshot
        assert snap is not None
        assert snap.get("pay_share_amount_inr") == 600.0
        assert transferred[0].reason_for_change == "Therapist relocated to another city"
    finally:
        db.close()

    timeline = client.get(f"/api/v1/admin/cases/{case_id}/timeline", headers=ah)
    assert timeline.status_code == 200
    items_tl = timeline.json()["items"]
    assert any("reassigned" in (i.get("action_label") or "").lower() for i in items_tl)
    assert any(
        i.get("detail")
        for i in items_tl
        if "reassigned" in (i.get("action_label") or "").lower()
    )


def test_billing_snapshot_report_columns():
    cols = billing_snapshot_report_columns(
        {
            "billing_type": "PER_SESSION",
            "client_rate_per_session_inr": 1000,
            "compensation_mode": "PERCENTAGE",
            "pay_share_amount_inr": 500,
        }
    )
    assert cols["Previous Billing Type"] == "PER SESSION"
    assert "1000" in cols["Previous Client Rate"]
    assert "500" in cols["Previous Therapist Pay"]
    assert "lumpsum" in cols["Previous Therapist Pay"]
    assert "share" not in cols["Previous Therapist Pay"].lower()
    assert cols["Previous Compensation Mode"] == "FIXED LUMP"
    assert "PERCENTAGE" not in cols["Previous Compensation Mode"]


def test_billing_snapshot_report_columns_prefers_fixed_lump():
    cols = billing_snapshot_report_columns(
        {
            "billing_type": "MONTHLY_FIXED",
            "client_monthly_rate_inr": 20000,
            "compensation_mode": "FIXED_LUMP",
            "therapist_fixed_pay_inr": 8000,
            "pay_share_amount_inr": 999,  # legacy leftover — ignored when fixed is set
        }
    )
    assert "8000" in cols["Previous Therapist Pay"]
    assert "999" not in cols["Previous Therapist Pay"]
    assert cols["Previous Compensation Mode"] == "FIXED LUMP"
