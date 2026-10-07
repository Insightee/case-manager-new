"""Therapist statement PDF export and missing package session count handling."""

from __future__ import annotations

import uuid
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.billing_calc_errors import MISSING_PACKAGE_COUNT_CODE
from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CaseStatus, CompensationMode
from app.models.child import Child
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services import invoice_billing_service as billing

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _package_case_with_assignment(db) -> tuple[User, Case]:
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    child = db.scalars(select(Child).limit(1)).first()
    assert therapist is not None and child is not None
    case = Case(
        case_code=f"PKG-PDF-{uuid.uuid4().hex[:8]}",
        child_id=child.id,
        service_type="Homecare",
        product_module="homecare",
        status=CaseStatus.ACTIVE,
        billing_type=BillingType.PACKAGE,
        package_session_count=10,
        package_amount_inr=25000,
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=15000,
    )
    db.add(case)
    db.flush()
    db.add(
        CaseAssignment(
            case_id=case.id,
            therapist_user_id=therapist.id,
            status=CaseAssignmentStatus.ACTIVE,
            start_date=date(2026, 1, 1),
        )
    )
    db.commit()
    db.refresh(case)
    return therapist, case


def _invoice_with_session(db, therapist: User, case: Case, ym: str = "2099-06") -> Invoice:
    created = billing.create_late_session(
        db,
        therapist.id,
        case_id=case.id,
        month=ym,
        session_date=date(2099, 6, 8),
        start_time=time(10, 0),
        end_time=time(11, 0),
        attendance_status="present",
        activities_done="PDF export fixture",
        observations=None,
        late_reason="Missing package count PDF test",
    )
    log = db.get(DailyLog, created["daily_log_id"])
    log.approval_status = LogApprovalStatus.APPROVED
    db.commit()

    preview = billing.build_month_preview(db, therapist.id, ym)
    inv = Invoice(
        therapist_user_id=therapist.id,
        month=preview["month_label"],
        amount_inr=preview["net_amount_inr"],
        subtotal_inr=preview["subtotal_inr"],
        leave_deduction_inr=preview.get("leave_deduction_inr") or 0,
        sessions_count=preview["total_sessions"],
        status=InvoiceStatus.IN_REVIEW,
    )
    db.add(inv)
    db.flush()
    billing._replace_invoice_lines_from_preview(db, inv, preview)
    db.commit()
    db.refresh(inv)
    return inv


def test_therapist_statement_pdf_download():
    headers = _login("therapist@demo.com")
    rows = client.get("/api/v1/invoices", headers=headers).json()
    assert isinstance(rows, list)
    if not rows:
        return
    inv_id = rows[0]["id"]
    r = client.get(f"/api/v1/invoices/{inv_id}/pdf", headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type") == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    assert "insighte_statement" in r.headers.get("content-disposition", "")


def test_therapist_statement_pdf_requires_own_invoice_or_finance():
    th_headers = _login("therapist@demo.com")
    rows = client.get("/api/v1/invoices", headers=th_headers).json()
    if not rows:
        return
    own = rows[0]
    ok = client.get(f"/api/v1/invoices/{own['id']}/pdf", headers=th_headers)
    assert ok.status_code == 200

    finance_h = _login("finance@demo.com")
    finance_ok = client.get(f"/api/v1/invoices/{own['id']}/pdf", headers=finance_h)
    assert finance_ok.status_code == 200


def test_pdf_export_missing_package_count_returns_422_not_500():
    db = SessionLocal()
    try:
        therapist, case = _package_case_with_assignment(db)
        inv = _invoice_with_session(db, therapist, case)
        case.package_session_count = None
        db.commit()
        inv_id = inv.id
        case_id = case.id
        case_code = case.case_code
    finally:
        db.close()

    headers = _login("therapist@demo.com")
    r = client.get(f"/api/v1/invoices/{inv_id}/pdf", headers=headers)
    assert r.status_code == 422, r.text
    body = r.json()
    detail = body.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == MISSING_PACKAGE_COUNT_CODE
    assert case_code in detail.get("message", "")
    assert detail.get("caseId") == case_id

    db = SessionLocal()
    try:
        row = db.get(Case, case_id)
        row.package_session_count = 10
        db.commit()
    finally:
        db.close()


def test_package_invoice_pdf_export_unchanged_amounts():
    db = SessionLocal()
    try:
        therapist, case = _package_case_with_assignment(db)
        inv = _invoice_with_session(db, therapist, case)
        breakdown = billing.invoice_breakdown(db, inv.id)
        expected_net = breakdown["net_amount_inr"]
        expected_subtotal = breakdown["subtotal_inr"]
        inv_id = inv.id
    finally:
        db.close()

    headers = _login("therapist@demo.com")
    r = client.get(f"/api/v1/invoices/{inv_id}/pdf", headers=headers)
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"

    db = SessionLocal()
    try:
        breakdown_after = billing.invoice_breakdown(db, inv_id)
        assert breakdown_after["net_amount_inr"] == pytest.approx(expected_net, rel=0.01)
        assert breakdown_after["subtotal_inr"] == pytest.approx(expected_subtotal, rel=0.01)
    finally:
        db.close()


def test_data_exceptions_lists_missing_package_session_count():
    db = SessionLocal()
    try:
        _therapist, case = _package_case_with_assignment(db)
        case.package_session_count = None
        db.commit()
        case_id = case.id
        case_code = case.case_code
    finally:
        db.close()

    headers = _login("superadmin@demo.com")
    res = client.get("/api/v1/admin/leadership/data-exceptions", headers=headers)
    assert res.status_code == 200
    rows = res.json().get("rows") or []
    match = [
        r
        for r in rows
        if r.get("rule") == "missing_package_session_count" and r.get("recordId") == case_id
    ]
    assert match, f"Expected missing_package_session_count for {case_code}"
    assert match[0]["label"] == case_code

    db = SessionLocal()
    try:
        row = db.get(Case, case_id)
        row.package_session_count = 10
        row.status = CaseStatus.DEACTIVATED
        for assignment in db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all():
            assignment.status = CaseAssignmentStatus.ENDED
        db.commit()
    finally:
        db.close()
