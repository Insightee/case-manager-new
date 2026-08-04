"""Client billing loop: gateway mock, package cycle rollover, late fee line."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.case import BillingType, Case
from app.models.client_billing import CarePackage, ClientInvoiceLineType
from app.models.client_package_cycle import ClientPackageCycle
from app.seed.demo_seed import run as seed_run
from app.services import client_package_cycle_service
from sqlalchemy import select

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_mock_gateway_success_and_receipt():
    seed_run()
    parent_h = _login("parent@demo.com")
    listed = client.get("/api/v1/parent/billing/invoices", headers=parent_h).json()
    targets = [i for i in listed if i.get("balanceInr", 0) > 0]
    if len(targets) < 1:
        return
    inv_id = targets[0]["id"]
    pay = client.post(f"/api/v1/parent/billing/invoices/{inv_id}/pay-gateway", headers=parent_h)
    assert pay.status_code == 200, pay.text
    body = pay.json()
    assert body.get("success") is True
    payment_id = body.get("paymentId")
    assert payment_id
    receipt = client.get(f"/api/v1/parent/billing/payments/{payment_id}/receipt", headers=parent_h)
    assert receipt.status_code == 200
    assert receipt.headers.get("content-type") == "application/pdf"
    assert receipt.content[:4] == b"%PDF"


def test_mock_gateway_fail_reference():
    parent_h = _login("parent@demo.com")
    listed = client.get("/api/v1/parent/billing/invoices", headers=parent_h).json()
    target = next((i for i in listed if i.get("balanceInr", 0) > 0), None)
    if not target:
        return
    fail = client.post(
        f"/api/v1/parent/billing/invoices/{target['id']}/pay-gateway?reference=TESTFAIL",
        headers=parent_h,
    )
    assert fail.status_code == 200
    assert fail.json().get("success") is False


def test_package_cycle_credit_forward_preview():
    db = SessionLocal()
    try:
        case = db.scalars(select(Case).where(Case.billing_type == BillingType.PACKAGE).limit(1)).first()
        if not case:
            case = db.scalars(select(Case).limit(1)).first()
        assert case is not None
        pkg = db.scalars(select(CarePackage).where(CarePackage.case_id == case.id).limit(1)).first()
        if not pkg:
            return
        pkg.total_sessions = 10
        pkg.used_sessions = 8
        db.commit()
        preview = client_package_cycle_service.renewal_preview(db, pkg, case)
        assert preview["remainingSessions"] == 2
        if not preview.get("needsReview"):
            assert preview.get("renewalBillableSessions") == 8
            assert "2 carried" in (preview.get("nextCyclePreview") or "")
    finally:
        db.close()


def test_admin_late_fee_additive_line():
    admin_h = _login("superadmin@demo.com")
    listed = client.get("/api/v1/admin/client-billing/invoices", headers=admin_h).json()
    if not listed:
        return
    inv_id = listed[0]["id"]
    before = client.get(f"/api/v1/admin/client-billing/invoices/{inv_id}", headers=admin_h).json()
    total_before = before.get("totalInr") or 0
    r = client.post(
        f"/api/v1/admin/client-billing/invoices/{inv_id}/late-fee?amount_inr=250&finance_note=Test+late",
        headers=admin_h,
    )
    assert r.status_code == 200, r.text
    after = client.get(f"/api/v1/admin/client-billing/invoices/{inv_id}", headers=admin_h).json()
    late_lines = [ln for ln in after.get("lines") or [] if ln.get("lineItemType") == ClientInvoiceLineType.LATE_FEE.value]
    assert late_lines, "Expected LATE_FEE line on invoice"
    assert late_lines[0].get("amountInr") == 250
