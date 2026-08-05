"""Finance money fixes — asserts against IC-WK walkthrough fixture."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.seed.finance_walkthrough_fixture import BILLING_MONTH, run as fixture_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed_finance_walkthrough_fixture():
    db = SessionLocal()
    try:
        from app.seed.finance_walkthrough_fixture import _cleanup_walkthrough_cases

        _cleanup_walkthrough_cases(db)
    finally:
        db.close()
    fixture_run(force=True)
    yield
    db = SessionLocal()
    try:
        from app.seed.finance_walkthrough_fixture import _cleanup_walkthrough_cases

        _cleanup_walkthrough_cases(db)
    finally:
        db.close()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _wk_case(db, code: str) -> Case:
    case = db.scalar(select(Case).where(Case.case_code == code))
    assert case is not None, f"Missing fixture case {code}"
    return case


def test_fixture_seeds_ten_walkthrough_cases():
    db = SessionLocal()
    try:
        codes = [c.case_code for c in db.scalars(select(Case).where(Case.case_code.like("IC-WK-%"))).all()]
        assert len(codes) >= 10
    finally:
        db.close()


def test_invoice_wrong_approve_creates_therapist_case_line():
    db = SessionLocal()
    try:
        case = _wk_case(db, "IC-WK-002")
        case_id = case.id
    finally:
        db.close()

    headers = _login("finance@demo.com")
    prop = client.post(
        "/api/v1/admin/finance-writable/corrections/correct-reshare",
        headers=headers,
        json={
            "case_id": case_id,
            "billing_month": BILLING_MONTH,
            "wrong_side": "INVOICE_WRONG",
            "reason": "Fixture: invoice sessions overstated",
        },
    )
    assert prop.status_code == 200, prop.text
    pid = prop.json()["id"]
    approved = client.post(f"/api/v1/admin/finance-writable/corrections/{pid}/approve", headers=headers, json={})
    assert approved.status_code == 200, approved.text
    assert approved.json()["clientResult"]["newTotalInr"] == 4800.0
    assert approved.json()["payoutResult"]["newPayoutInr"] == 2880.0


def test_package_drawdown_not_false_block():
    headers = _login("finance@demo.com")
    sheet = client.get(
        f"/api/v1/admin/finance-control-tower/billing-readiness-master-sheet?billing_month={BILLING_MONTH}&limit=50",
        headers=headers,
    )
    assert sheet.status_code == 200, sheet.text
    row = next(r for r in sheet.json()["items"] if r["caseCode"] == "IC-WK-004")
    assert row["activity"]["sessionsDelivered"] == 8
    assert row["exceptionState"] != "BLOCK"


def test_deduction_ladder_never_negative():
    db = SessionLocal()
    try:
        case = _wk_case(db, "IC-WK-002")
        case_id = case.id
        from app.models.assignment import CaseAssignment, CaseAssignmentStatus

        therapist_id = db.scalar(
            select(CaseAssignment.therapist_user_id)
            .where(CaseAssignment.case_id == case_id, CaseAssignment.status == CaseAssignmentStatus.ACTIVE)
            .limit(1)
        )
    finally:
        db.close()

    headers = _login("finance@demo.com")
    listed = client.get(
        f"/api/v1/admin/finance-writable/deductions?case_id={case_id}&billing_month={BILLING_MONTH}",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    ladder = listed.json()["payoutLadder"]
    assert ladder["grossInr"] == 2880.0
    assert ladder["netInr"] >= 0

    blocked = client.post(
        "/api/v1/admin/finance-writable/deductions",
        headers=headers,
        json={
            "case_id": case_id,
            "billing_month": BILLING_MONTH,
            "therapist_user_id": therapist_id,
            "amount_inr": 5000,
            "direction": "DEDUCT",
            "reason": "Should block — exceeds gross",
            "note_type": "DEDUCTION",
        },
    )
    assert blocked.status_code == 400


def test_outstanding_surfaces_agree_on_fixture_month():
    headers = _login("finance@demo.com")
    month = BILLING_MONTH

    rec = client.get(f"/api/v1/admin/client-billing/receivables?month={month}", headers=headers).json()
    summary = client.get(f"/api/v1/admin/client-billing/summary?month={month}", headers=headers).json()
    brief = client.get(f"/api/v1/admin/finance-overview/monday-brief?billing_month={month}", headers=headers).json()
    tower = client.get(
        f"/api/v1/admin/finance-control-tower/summary?billing_month={month}", headers=headers
    ).json()

    outstanding = rec["totals"]["outstandingInr"]
    assert summary["totalOutstandingInr"] == outstanding
    assert brief["moneyIn"]["collectibleOutstandingInr"] == outstanding
    assert tower["financeSummary"]["outstanding"]["value"] == outstanding


def test_parent_month_scope_matches_receivables():
    headers = _login("parent@demo.com")
    dash = client.get(f"/api/v1/admin/client-billing/receivables?month={BILLING_MONTH}", headers=_login("finance@demo.com")).json()
    parent = client.get(f"/api/v1/parent/billing/dashboard?month={BILLING_MONTH}", headers=headers).json()
    assert parent["summary"]["dueTotalInr"] == dash["totals"]["outstandingInr"]


def test_payment_claims_list_on_invoices_tab():
    headers = _login("finance@demo.com")
    invs = client.get(
        f"/api/v1/admin/client-billing/invoices?month={BILLING_MONTH}&claims_pending=true",
        headers=headers,
    )
    assert invs.status_code == 200, invs.text
    assert any(i.get("invoiceNumber") == "INV-WK-009" for i in invs.json())


def test_crm_note_surfaces_on_master_sheet():
    headers = _login("finance@demo.com")
    sheet = client.get(
        f"/api/v1/admin/finance-control-tower/billing-readiness-master-sheet?billing_month={BILLING_MONTH}&limit=50",
        headers=headers,
    )
    row = next(r for r in sheet.json()["items"] if r["caseCode"] == "IC-WK-001")
    assert "RETAINER" in row["comments"]["crm"]


def test_clean_row_clear_pill():
    headers = _login("finance@demo.com")
    sheet = client.get(
        f"/api/v1/admin/finance-control-tower/billing-readiness-master-sheet?billing_month={BILLING_MONTH}&limit=50",
        headers=headers,
    )
    row = next(r for r in sheet.json()["items"] if r["caseCode"] == "IC-WK-001")
    assert row["exceptionState"] == "CLEAR"
