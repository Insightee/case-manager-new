"""Stage 2 client billing: engine-aware composer, Zoho seam, runtime config."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.billing_step6 import BillingCalcException
from app.models.case import Case
from app.models.ledger_billing import BillableStatus, BillingLedger, LedgerEventType, LedgerSourceType
from app.seed.demo_seed import run as seed_run
from app.services import billing_composer_service, zoho_client_sync

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _first_case_id() -> int:
    db = SessionLocal()
    try:
        case = db.query(Case).first()
        assert case is not None
        return int(case.id)
    finally:
        db.close()


def test_runtime_config_coherent_answer(monkeypatch):
    monkeypatch.setattr(settings, "enable_billing", True)
    monkeypatch.setattr(settings, "billing_ledger_writes", False)
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    monkeypatch.setattr(settings, "zoho_books_api_key", "")
    headers = _login("finance@demo.com")
    res = client.get("/api/v1/admin/client-billing/runtime-config", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["billingEnabled"] is True
    assert body["ledgerWritesEnabled"] is False
    assert body["cutoverComplete"] is False
    assert body["provisional"] is True
    assert body["zohoConfigured"] is False


def test_parent_runtime_config_no_write_secrets(monkeypatch):
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    headers = _login("parent@demo.com")
    res = client.get("/api/v1/parent/billing/runtime-config", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["provisional"] is True
    assert "zohoConfigured" not in body
    assert "ledgerWritesEnabled" not in body


def test_zoho_seam_not_configured_without_key(monkeypatch):
    monkeypatch.setattr(settings, "zoho_books_api_key", "")
    out = zoho_client_sync.sync_client_invoice(42)
    assert out["status"] == "not_configured"
    assert out["externalId"] is None


def test_zoho_seam_attempts_with_dummy_key(monkeypatch):
    monkeypatch.setattr(settings, "zoho_books_api_key", "dummy-key")
    out = zoho_client_sync.sync_client_invoice(42)
    assert out["status"] == "attempted"
    assert out["invoiceId"] == 42


def test_blocking_exception_sets_can_build_false(monkeypatch):
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    case_id = _first_case_id()
    ym = date.today().strftime("%Y-%m")
    db = SessionLocal()
    try:
        db.add(
            BillingCalcException(
                case_id=case_id,
                ledger_month=ym,
                code="MISSING_PACKAGE_COUNT",
                message="Package session count is missing",
                resolved=False,
            )
        )
        db.commit()
        blocking = billing_composer_service.blocking_calc_exceptions_for_case(
            db, case_id=case_id, billing_month=ym
        )
        assert blocking
        assert blocking[0]["code"] == "MISSING_PACKAGE_COUNT"
        preview = billing_composer_service.get_composer_preview(
            db, case_id=case_id, billing_month=ym
        )
        assert preview["canBuild"] is False
        assert preview["overview"]["confidence"] != "RECONCILED"
        assert preview["provisional"] is True
    finally:
        db.close()


def test_build_from_ledger_blocked_by_exception(monkeypatch):
    monkeypatch.setattr(settings, "enable_billing", True)
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    case_id = _first_case_id()
    ym = date.today().strftime("%Y-%m")
    db = SessionLocal()
    try:
        db.add(
            BillingCalcException(
                case_id=case_id,
                ledger_month=ym,
                code="ASSIGNMENT_GAP",
                message="Assignment gap blocks billing",
                resolved=False,
            )
        )
        db.commit()
    finally:
        db.close()
    headers = _login("superadmin@demo.com")
    r = client.post(
        f"/api/v1/admin/client-billing/cases/{case_id}/build-from-ledger?billing_month={ym}",
        headers=headers,
    )
    assert r.status_code == 409
    assert "calculation exception" in r.json().get("detail", "").lower()


def test_pending_finance_draft_requires_explicit_post(monkeypatch):
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    case_id = _first_case_id()
    ym = date.today().strftime("%Y-%m")
    db = SessionLocal()
    try:
        db.add(
            BillingLedger(
                case_id=case_id,
                source_type=LedgerSourceType.MONTHLY_FEE,
                source_id=None,
                ledger_month=ym,
                event_date=date.today().replace(day=1),
                event_type=LedgerEventType.MONTHLY_FEE,
                billable_status=BillableStatus.PENDING_FINANCE,
                quantity=1,
                rate_inr=5000,
                amount_inr=5000,
                total_inr=5000,
            )
        )
        db.commit()
        drafts = billing_composer_service.postable_draft_charges_for_case(
            db, case_id=case_id, billing_month=ym
        )
        assert len(drafts) >= 1
        assert all(d["requiresExplicitPost"] for d in drafts)
        preview = billing_composer_service.get_composer_preview(
            db, case_id=case_id, billing_month=ym
        )
        assert any(d["billableStatus"] == "PENDING_FINANCE" for d in preview["postableDraftCharges"])
    finally:
        db.close()


def test_parent_invoice_detail_still_isolates_payout_fields():
    headers = _login("parent@demo.com")
    listed = client.get("/api/v1/parent/billing/invoices", headers=headers)
    assert listed.status_code == 200
    invs = listed.json()
    if not invs:
        pytest.skip("No parent invoices")
    inv_id = invs[0]["id"]
    detail = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=headers)
    assert detail.status_code == 200
    text = detail.text.lower().replace("_", "")
    assert "therapistpayout" not in text
    assert "estimatedmargin" not in text


def test_build_from_ledger_blocked_when_writes_disabled(monkeypatch):
    """Staging PASS 2 posture: preview OK, money mutations rejected."""
    # Login while app_env is still test (memory Redis). Gate1 pattern.
    headers = _login("superadmin@demo.com")
    case_id = _first_case_id()
    ym = date.today().strftime("%Y-%m")
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "enable_billing", True)
    monkeypatch.setattr(settings, "billing_ledger_writes", False)
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    r = client.post(
        f"/api/v1/admin/client-billing/cases/{case_id}/build-from-ledger?billing_month={ym}",
        headers=headers,
    )
    assert r.status_code == 403
    assert "ledger writes" in r.json().get("detail", "").lower()


def test_post_pending_finance_blocked_when_writes_disabled(monkeypatch):
    headers = _login("superadmin@demo.com")
    case_id = _first_case_id()
    ym = date.today().strftime("%Y-%m")
    db = SessionLocal()
    try:
        row = BillingLedger(
            case_id=case_id,
            source_type=LedgerSourceType.MONTHLY_FEE,
            source_id=None,
            ledger_month=ym,
            event_date=date.today().replace(day=1),
            event_type=LedgerEventType.MONTHLY_FEE,
            billable_status=BillableStatus.PENDING_FINANCE,
            quantity=1,
            rate_inr=1000,
            amount_inr=1000,
            total_inr=1000,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        ledger_id = row.id
    finally:
        db.close()
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "enable_billing", True)
    monkeypatch.setattr(settings, "billing_ledger_writes", False)
    r = client.post(
        f"/api/v1/admin/ledger-billing/ledger/{ledger_id}/post-finance",
        headers=headers,
    )
    assert r.status_code == 403
    assert "ledger writes" in r.json().get("detail", "").lower()
