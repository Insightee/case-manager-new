"""Finance writable Loop 2 — correction proposals, linked edits, deductions, notes."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.client_billing import ClientInvoice, ClientInvoiceType
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine, InvoiceSessionLine, SessionLineSource, SessionLineType
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services import finance_correction_service, finance_payout_deduction_service

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _case_with_share_ratio(db) -> Case:
    case = db.scalar(select(Case).where(Case.pay_share_amount_inr.is_not(None)).limit(1))
    assert case is not None
    assert case.client_rate_per_session_inr or case.client_monthly_rate_inr or case.package_amount_inr
    ratio = finance_correction_service.case_share_ratio(case)
    assert ratio is not None, "Need case with computable share ratio"
    return case


def _setup_case_month_invoice_and_payout(db, *, case: Case, billing_month: str = "2099-07"):
    therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
    parent = db.scalar(select(User).where(User.email == "parent@demo.com"))
    assert therapist is not None and parent is not None

    inv = ClientInvoice(
        invoice_number=f"INV-TEST-{case.id}-{billing_month}",
        parent_user_id=parent.id,
        case_id=case.id,
        invoice_type=ClientInvoiceType.POSTPAID,
        status="GENERATED",
        billing_month=billing_month,
        service_type=case.service_type or "Homecare",
        product_module=case.product_module or "homecare",
        due_date=date(2099, 7, 10),
        subtotal_inr=4800,
        tax_inr=0,
        discount_inr=0,
        package_deduction_inr=0,
        adjustment_inr=0,
        total_inr=4800,
        amount_paid_inr=0,
    )
    db.add(inv)
    db.flush()

    payout_share = finance_correction_service.payout_from_client_amount(
        4800, finance_correction_service.case_share_ratio(case)
    )
    tinv = Invoice(
        therapist_user_id=therapist.id,
        month=billing_month,
        amount_inr=payout_share,
        subtotal_inr=payout_share,
        status=InvoiceStatus.IN_REVIEW,
        sessions_count=1,
    )
    db.add(tinv)
    db.flush()
    cl = InvoiceCaseLine(
        invoice_id=tinv.id,
        case_id=case.id,
        case_code=case.case_code or f"C-{case.id}",
        billing_type="PER_SESSION",
        included_sessions=1,
        therapist_share_inr=payout_share,
    )
    db.add(cl)
    db.flush()
    db.add(
        InvoiceSessionLine(
            invoice_case_line_id=cl.id,
            session_id=None,
            session_date=date(2099, 7, 15),
            line_type=SessionLineType.PER_SESSION,
            amount_inr=payout_share,
            source=SessionLineSource.LOG,
            included=True,
        )
    )
    db.commit()
    return inv.id, tinv.id, payout_share


def test_case_share_ratio_blocks_when_missing():
    seed_run()
    db = SessionLocal()
    try:
        case = db.scalar(select(Case).limit(1))
        case.pay_share_amount_inr = None
        case.therapist_fixed_pay_inr = None
        case.client_rate_per_session_inr = None
        case.client_monthly_rate_inr = None
        case.package_amount_inr = None
        db.commit()
        assert finance_correction_service.case_share_ratio(case) is None
    finally:
        db.close()


def test_linked_edit_confirm_four_numbers_and_approve_atomic():
    seed_run()
    db = SessionLocal()
    try:
        case = _case_with_share_ratio(db)
        case_id = case.id
        inv_id, tinv_id, old_payout = _setup_case_month_invoice_and_payout(db, case=case)
        ratio = finance_correction_service.case_share_ratio(case)
        new_client = 5000.0
        expected_payout = finance_correction_service.payout_from_client_amount(new_client, ratio)
    finally:
        db.close()

    headers = _login("finance@demo.com")
    create = client.post(
        "/api/v1/admin/finance-writable/corrections/linked-amount-edit",
        headers=headers,
        json={
            "case_id": case_id,
            "billing_month": "2099-07",
            "new_client_amount_inr": new_client,
            "reason": "Reconciliation diff — invoice sessions undercounted",
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["status"] == "PENDING"
    confirm = body["confirmScreen"]
    assert confirm["oldClientAmountInr"] == 4800.0
    assert confirm["newClientAmountInr"] == new_client
    assert confirm["oldPayoutAmountInr"] == old_payout
    assert confirm["newPayoutAmountInr"] == expected_payout
    assert confirm["reasonRequired"] is True

    proposal_id = body["id"]
    approve = client.post(
        f"/api/v1/admin/finance-writable/corrections/{proposal_id}/approve",
        headers=headers,
    )
    assert approve.status_code == 200, approve.text
    approved = approve.json()
    assert approved["clientResult"]["newTotalInr"] == new_client
    assert approved["payoutResult"]["newPayoutInr"] == expected_payout

    db = SessionLocal()
    try:
        inv_db = db.get(ClientInvoice, inv_id)
        assert float(inv_db.total_inr) == new_client
        snap = inv_db.billing_snapshot or {}
        assert "financeCorrectionReason" in snap
        tinv_db = db.get(Invoice, tinv_id)
        cl = db.scalar(select(InvoiceCaseLine).where(InvoiceCaseLine.invoice_id == tinv_id))
        assert float(cl.therapist_share_inr) == expected_payout
        assert float(tinv_db.amount_inr) == expected_payout
        assert "Finance correction" in (tinv_db.notes or "")
    finally:
        db.close()


def test_reject_second_edit_nothing_moves():
    seed_run()
    db = SessionLocal()
    try:
        case = _case_with_share_ratio(db)
        case_id = case.id
        inv_id, tinv_id, old_payout = _setup_case_month_invoice_and_payout(db, case=case, billing_month="2099-08")
        original_total = 4800.0
    finally:
        db.close()

    headers = _login("finance@demo.com")
    create = client.post(
        "/api/v1/admin/finance-writable/corrections/linked-amount-edit",
        headers=headers,
        json={
            "case_id": case_id,
            "billing_month": "2099-08",
            "new_client_amount_inr": 6000.0,
            "reason": "Proposed correction to reject",
        },
    )
    assert create.status_code == 200, create.text
    proposal_id = create.json()["id"]
    reject = client.post(
        f"/api/v1/admin/finance-writable/corrections/{proposal_id}/reject",
        headers=headers,
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "REJECTED"

    db = SessionLocal()
    try:
        inv_db = db.get(ClientInvoice, inv_id)
        assert float(inv_db.total_inr) == original_total
        tinv_db = db.get(Invoice, tinv_id)
        cl = db.scalar(select(InvoiceCaseLine).where(InvoiceCaseLine.invoice_id == tinv_id))
        assert float(cl.therapist_share_inr) == old_payout
        assert float(tinv_db.amount_inr) == old_payout
    finally:
        db.close()


def test_correct_reshare_invoice_wrong_explicit_side():
    seed_run()
    db = SessionLocal()
    try:
        case = _case_with_share_ratio(db)
        case_id = case.id
        _setup_case_month_invoice_and_payout(db, case=case, billing_month="2099-09")
    finally:
        db.close()

    headers = _login("finance@demo.com")
    preview = client.post(
        "/api/v1/admin/finance-writable/corrections/preview-correct-reshare",
        headers=headers,
        json={"case_id": case_id, "billing_month": "2099-09", "wrong_side": "INVOICE_WRONG"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["wrongSide"] == "INVOICE_WRONG"

    create = client.post(
        "/api/v1/admin/finance-writable/corrections/correct-reshare",
        headers=headers,
        json={
            "case_id": case_id,
            "billing_month": "2099-09",
            "wrong_side": "INVOICE_WRONG",
            "reason": "Invoice wrong — aligning to activity record",
        },
    )
    assert create.status_code == 200, create.text
    assert create.json()["wrongSide"] == "INVOICE_WRONG"
    assert create.json()["proposalType"] == "CORRECT_RESHARE"


def test_deduction_after_tds_in_ladder():
    ladder = finance_payout_deduction_service.compute_payout_ladder(
        gross_inr=10000,
        tds_rate_percent=10,
        deductions=[
            {"amountInr": 500, "direction": "DEDUCT", "status": "ACTIVE"},
        ],
    )
    assert ladder["grossInr"] == 10000
    assert ladder["tdsInr"] == 1000
    assert ladder["afterTdsInr"] == 9000
    assert ladder["deductionsInr"] == 500
    assert ladder["netInr"] == 8500


def test_create_deduction_via_api():
    seed_run()
    db = SessionLocal()
    try:
        case = _case_with_share_ratio(db)
        case_id = case.id
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        therapist_id = therapist.id
        _setup_case_month_invoice_and_payout(db, case=case, billing_month="2099-07")
    finally:
        db.close()

    headers = _login("finance@demo.com")
    r = client.post(
        "/api/v1/admin/finance-writable/deductions",
        headers=headers,
        json={
            "case_id": case_id,
            "billing_month": "2099-07",
            "therapist_user_id": therapist_id,
            "amount_inr": 200,
            "direction": "DEDUCT",
            "reason": "Equipment recovery",
            "note_type": "DEDUCTION",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["amountInr"] == 200


def test_structured_crm_note_on_master_sheet():
    seed_run()
    db = SessionLocal()
    try:
        case = _case_with_share_ratio(db)
        case_id = case.id
    finally:
        db.close()

    headers = _login("finance@demo.com")
    note = client.post(
        "/api/v1/admin/finance-writable/notes",
        headers=headers,
        json={
            "case_id": case_id,
            "note_scope": "CRM",
            "note_type": "RETAINER",
            "reason": "Retainer rollover discussed with family",
            "billing_month": "2026-05",
        },
    )
    assert note.status_code == 200, note.text

    sheet = client.get(
        "/api/v1/admin/finance-control-tower/billing-readiness-master-sheet?billing_month=2026-05&limit=50",
        headers=headers,
    )
    assert sheet.status_code == 200, sheet.text
    rows = [r for r in sheet.json()["items"] if r["caseId"] == case_id]
    if rows:
        assert "RETAINER" in rows[0]["comments"]["crm"]


def test_missing_ratio_blocks_linked_edit():
    seed_run()
    db = SessionLocal()
    try:
        case = db.scalar(select(Case).limit(1))
        case.pay_share_amount_inr = None
        case.therapist_fixed_pay_inr = None
        db.commit()
        case_id = case.id
    finally:
        db.close()

    headers = _login("finance@demo.com")
    r = client.post(
        "/api/v1/admin/finance-writable/corrections/linked-amount-edit",
        headers=headers,
        json={
            "case_id": case_id,
            "billing_month": "2026-05",
            "new_client_amount_inr": 5000,
            "reason": "Should block",
        },
    )
    assert r.status_code == 400
    assert "share ratio" in r.json()["detail"].lower()
