"""Therapist payout settlement E2E — IC-WK-011..014 fixture cases + money-out guards."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CaseStatus, ClientBillingMode, CompensationMode
from app.models.child import Child
from app.models.external_ref import ExternalRef
from app.models.finance_writable import (
    FinancePayoutDeduction,
    FinancePayoutDeductionDirection,
    CaseFinanceNoteType,
)
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine
from app.models.therapist_payout_settlement import TherapistPayoutBatch, TherapistPayoutTransfer
from app.models.user import User
from app.seed.demo_seed import ensure_active_case_assignment, get_or_create_user
from app.seed.finance_walkthrough_fixture import BILLING_MONTH, _cleanup_walkthrough_cases, run as fixture_run
from app.core.permissions import RoleName

client = TestClient(app)


@pytest.fixture(scope="module")
def finance_walkthrough_data():
    fixture_run(force=True)
    yield
    db = SessionLocal()
    try:
        _cleanup_walkthrough_cases(db)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_ic_wk_payout_export_state(finance_walkthrough_data):
    """Isolate export tests — each test gets clean APPROVED invoices for IC-WK-011..013."""
    db = SessionLocal()
    try:
        inv_ids = list(
            db.scalars(
                select(Invoice.id)
                .join(InvoiceCaseLine, InvoiceCaseLine.invoice_id == Invoice.id)
                .where(
                    InvoiceCaseLine.case_code.in_(("IC-WK-011", "IC-WK-012", "IC-WK-013")),
                    Invoice.month == BILLING_MONTH,
                )
            ).all()
        )
        if inv_ids:
            db.query(TherapistPayoutTransfer).filter(TherapistPayoutTransfer.invoice_id.in_(inv_ids)).delete(
                synchronize_session=False
            )
            for inv in db.scalars(select(Invoice).where(Invoice.id.in_(inv_ids))).all():
                inv.status = InvoiceStatus.APPROVED
                inv.paid_amount_inr = None
            db.query(TherapistPayoutBatch).filter(
                TherapistPayoutBatch.idempotency_key.like("wk-%")
            ).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(autouse=True)
def _enable_payout_flags(monkeypatch, finance_walkthrough_data):
    monkeypatch.setattr(settings, "billing_ledger_writes", True)
    monkeypatch.setattr(settings, "payout_export_enabled", True)
    monkeypatch.setattr(settings, "payout_release_enabled", False)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _invoice_for_case(code: str) -> int:
    db = SessionLocal()
    try:
        case_line = db.scalar(
            select(InvoiceCaseLine)
            .join(Invoice, InvoiceCaseLine.invoice_id == Invoice.id)
            .where(InvoiceCaseLine.case_code == code, Invoice.month == BILLING_MONTH)
            .order_by(Invoice.id.desc())
        )
        assert case_line is not None, f"No therapist invoice for {code}"
        return case_line.invoice_id
    finally:
        db.close()


def test_settlement_preview_ic_wk_011():
    inv_id = _invoice_for_case("IC-WK-011")
    headers = _login("finance@demo.com")
    preview = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_id}",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["grossInr"] == 10000.0
    assert body["tdsInr"] == 1000.0
    assert body["netInr"] == 9000.0
    assert body["blocked"] is False


def test_settlement_preview_ic_wk_012_nonround_tds():
    inv_id = _invoice_for_case("IC-WK-012")
    headers = _login("finance@demo.com")
    preview = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_id}",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["grossInr"] == 3333.0
    assert body["tdsInr"] == 333.3
    assert body["netInr"] == 2999.7


def test_settlement_preview_ic_wk_013_deduction():
    inv_id = _invoice_for_case("IC-WK-013")
    headers = _login("finance@demo.com")
    preview = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_id}",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["grossInr"] == 10000.0
    assert body["deductionsInr"] == 500.0
    assert body["netInr"] == 8500.0


def test_ic_wk_014_blocks_export_with_zero_transfers():
    inv_id = _invoice_for_case("IC-WK-014")
    headers = _login("finance@demo.com")
    preview = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_id}",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["blocked"] is True

    db = SessionLocal()
    try:
        before = db.scalar(
            select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.invoice_id == inv_id)
        )
        assert before is None
    finally:
        db.close()

    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": "wk-014-blocked-export"},
    )
    assert export.status_code == 400

    db = SessionLocal()
    try:
        after = db.scalar(
            select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.invoice_id == inv_id)
        )
        assert after is None
    finally:
        db.close()


def test_mock_export_creates_transfers_and_external_refs():
    inv_id = _invoice_for_case("IC-WK-013")
    headers = _login("finance@demo.com")
    key = "wk-013-export-001"
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key, "billing_month": BILLING_MONTH},
    )
    assert export.status_code == 200, export.text
    batch = export.json()["batch"]
    assert batch["transferCount"] == 1
    assert export.json()["alreadyExported"] is False

    db = SessionLocal()
    try:
        inv = db.get(Invoice, inv_id)
        assert inv.status == InvoiceStatus.EXPORTING
        xfer = db.scalar(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.invoice_id == inv_id))
        assert xfer is not None
        ext = db.scalar(
            select(ExternalRef).where(
                ExternalRef.provider == "RAZORPAY_PAYOUT",
                ExternalRef.entity_type == "therapist_payout_transfer",
                ExternalRef.entity_id == xfer.id,
            )
        )
        assert ext is not None
    finally:
        db.close()


def test_idempotent_reexport_same_key():
    inv_id = _invoice_for_case("IC-WK-012")
    headers = _login("finance@demo.com")
    key = "wk-012-idempotent"
    first = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert second.status_code == 200, second.text
    assert second.json()["alreadyExported"] is True

    db = SessionLocal()
    try:
        batches = db.scalars(select(TherapistPayoutBatch).where(TherapistPayoutBatch.idempotency_key == key)).all()
        assert len(batches) == 1
        transfers = db.scalars(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.invoice_id == inv_id)).all()
        assert len(transfers) == 1
    finally:
        db.close()


def test_double_export_different_keys_rejected():
    inv_id = _invoice_for_case("IC-WK-011")
    headers = _login("finance@demo.com")
    first = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": "wk-011-first-export"},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": "wk-011-second-export-different"},
    )
    assert second.status_code == 400, second.text

    db = SessionLocal()
    try:
        transfers = db.scalars(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.invoice_id == inv_id)).all()
        assert len(transfers) == 1
    finally:
        db.close()


def test_idempotency_replay_mismatch_returns_409():
    inv_11 = _invoice_for_case("IC-WK-011")
    inv_12 = _invoice_for_case("IC-WK-012")
    headers = _login("finance@demo.com")
    key = "wk-mismatch-key"
    first = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_11], "idempotency_key": key},
    )
    assert first.status_code == 200, first.text

    replay = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_12], "idempotency_key": key},
    )
    assert replay.status_code == 409, replay.text


def test_status_sync_marks_paid_when_release_enabled(monkeypatch):
    monkeypatch.setattr(settings, "payout_release_enabled", True)
    inv_id = _invoice_for_case("IC-WK-012")
    headers = _login("finance@demo.com")
    key = "wk-012-sync-paid"
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert export.status_code == 200, export.text
    batch_id = export.json()["batch"]["id"]
    sync = client.post(f"/api/v1/admin/therapist-payouts/batches/{batch_id}/sync-status", headers=headers)
    assert sync.status_code == 200, sync.text
    assert sync.json()["status"] == "PAID"

    db = SessionLocal()
    try:
        inv = db.get(Invoice, inv_id)
        assert inv is not None
        assert inv.status == InvoiceStatus.PAID
    finally:
        db.close()


def test_sync_blocked_when_release_disabled():
    inv_id = _invoice_for_case("IC-WK-012")
    headers = _login("finance@demo.com")
    key = "wk-012-sync-blocked"
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert export.status_code == 200, export.text
    batch_id = export.json()["batch"]["id"]
    sync = client.post(f"/api/v1/admin/therapist-payouts/batches/{batch_id}/sync-status", headers=headers)
    assert sync.status_code == 403, sync.text

    db = SessionLocal()
    try:
        inv = db.get(Invoice, inv_id)
        assert inv.status != InvoiceStatus.PAID
    finally:
        db.close()


def test_mock_failure_returns_invoice_to_queue(monkeypatch):
    inv_id = _invoice_for_case("IC-WK-011")
    headers = _login("finance@demo.com")

    from app.services import payout_provider

    class FailXferMock(payout_provider.MockRazorpayPayoutProvider):
        def create_batch(self, *, transfers, idempotency_key):
            result = super().create_batch(transfers=transfers, idempotency_key=idempotency_key)
            result.transfers = [
                {**t, "status": "failed", "providerRef": f"{t['providerRef']}-FAIL"}
                for t in result.transfers
            ]
            return result

    monkeypatch.setattr("app.services.payout_batch_service.get_payout_provider", lambda: FailXferMock())

    key = "wk-011-fail-return"
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert export.status_code == 200, export.text

    db = SessionLocal()
    try:
        inv = db.get(Invoice, inv_id)
        assert inv is not None
        assert inv.status == InvoiceStatus.APPROVED
        xfer = db.scalar(
            select(TherapistPayoutTransfer)
            .where(TherapistPayoutTransfer.invoice_id == inv_id)
            .order_by(TherapistPayoutTransfer.id.desc())
        )
        assert xfer is not None
        assert xfer.status == "FAILED"
    finally:
        db.close()

    # Re-eligible after FAILED — new export with different key should succeed.
    retry = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": "wk-011-retry-after-fail"},
    )
    assert retry.status_code == 200, retry.text


def test_unapproved_statement_export_rejected():
    db = SessionLocal()
    try:
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        inv = Invoice(
            therapist_user_id=therapist.id,
            month="2099-12",
            amount_inr=100,
            subtotal_inr=100,
            status=InvoiceStatus.IN_REVIEW,
            sessions_count=0,
        )
        db.add(inv)
        db.flush()
        inv_id = inv.id
        db.commit()
    finally:
        db.close()

    headers = _login("finance@demo.com")
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": "unapproved-block"},
    )
    assert export.status_code == 400


def test_transition_case_deductions_therapist_scoped():
    db = SessionLocal()
    try:
        therapist_a = get_or_create_user(
            db, "transition-a@demo.com", "demo123", "Transition Therapist A", RoleName.THERAPIST
        )
        therapist_b = get_or_create_user(
            db, "transition-b@demo.com", "demo123", "Transition Therapist B", RoleName.THERAPIST
        )
        case_mgr = db.scalar(select(User).where(User.email == "casemanager@demo.com"))
        child = Child(first_name="Transition", last_name="Case")
        db.add(child)
        db.flush()
        case = Case(
            case_code="IC-WK-TRANS",
            child_id=child.id,
            service_type="Homecare",
            product_module="homecare",
            status=CaseStatus.ACTIVE,
            case_manager_user_id=case_mgr.id,
            client_billing_mode=ClientBillingMode.POSTPAID,
            billing_type=BillingType.PER_SESSION,
            client_rate_per_session_inr=5000,
            pay_share_amount_inr=3000,
            compensation_mode=CompensationMode.PERCENTAGE,
        )
        db.add(case)
        db.flush()
        ensure_active_case_assignment(
            db,
            case_id=case.id,
            therapist_user_id=therapist_a.id,
            assigned_by_user_id=case_mgr.id,
            start_date=date(2026, 8, 1),
        )
        ensure_active_case_assignment(
            db,
            case_id=case.id,
            therapist_user_id=therapist_b.id,
            assigned_by_user_id=case_mgr.id,
            start_date=date(2026, 8, 15),
        )

        inv_a = Invoice(
            therapist_user_id=therapist_a.id,
            month=BILLING_MONTH,
            amount_inr=3000,
            subtotal_inr=3000,
            status=InvoiceStatus.APPROVED,
            sessions_count=1,
        )
        inv_b = Invoice(
            therapist_user_id=therapist_b.id,
            month=BILLING_MONTH,
            amount_inr=3000,
            subtotal_inr=3000,
            status=InvoiceStatus.APPROVED,
            sessions_count=1,
        )
        db.add(inv_a)
        db.add(inv_b)
        db.flush()
        for inv in (inv_a, inv_b):
            db.add(
                InvoiceCaseLine(
                    invoice_id=inv.id,
                    case_id=case.id,
                    case_code=case.case_code,
                    billing_type="PER_SESSION",
                    included_sessions=1,
                    therapist_share_inr=3000,
                )
            )
        db.add(
            FinancePayoutDeduction(
                case_id=case.id,
                billing_month=BILLING_MONTH,
                therapist_user_id=therapist_a.id,
                therapist_invoice_id=inv_a.id,
                amount_inr=200,
                direction=FinancePayoutDeductionDirection.DEDUCT,
                reason="Transition month deduction — therapist A only",
                note_type=CaseFinanceNoteType.TRANSITION,
                created_by_user_id=case_mgr.id,
            )
        )
        db.commit()
        inv_a_id, inv_b_id = inv_a.id, inv_b.id
    finally:
        db.close()

    headers = _login("finance@demo.com")
    preview_a = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_a_id}", headers=headers
    )
    preview_b = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_b_id}", headers=headers
    )
    assert preview_a.status_code == 200, preview_a.text
    assert preview_b.status_code == 200, preview_b.text
    assert preview_a.json()["deductionsInr"] == 200.0
    assert preview_b.json()["deductionsInr"] == 0.0
    assert preview_a.json()["netInr"] == 2500.0  # 3000 gross - 300 TDS - 200 deduction
    assert preview_b.json()["netInr"] == 2700.0  # 3000 - 300 TDS, no cross-therapist leak


def test_rbac_export_sync_finance_writable_only():
    headers = _login("finance@demo.com")
    inv_id = _invoice_for_case("IC-WK-011")
    assert (
        client.post(
            "/api/v1/admin/therapist-payouts/export-batch",
            headers=headers,
            json={"invoice_ids": [inv_id], "idempotency_key": "rbac-finance-ok"},
        ).status_code
        == 200
    )

    for email in ("parent@demo.com", "therapist@demo.com"):
        blocked = _login(email)
        assert (
            client.post(
                "/api/v1/admin/therapist-payouts/export-batch",
                headers=blocked,
                json={"invoice_ids": [inv_id], "idempotency_key": "rbac-blocked"},
            ).status_code
            == 403
        )

    admin_h = _login("admin@demo.com")
    assert (
        client.post(
            "/api/v1/admin/therapist-payouts/export-batch",
            headers=admin_h,
            json={"invoice_ids": [inv_id], "idempotency_key": "rbac-admin-blocked"},
        ).status_code
        == 403
    )
