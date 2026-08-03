"""Stage 1 Finance Control Tower — RBAC, confidence, zero-write proofs."""
from __future__ import annotations

import hashlib
import inspect

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.client_billing import ClientInvoice, ClientPayment
from app.models.invoice import Invoice
from app.models.ledger_billing import BillingLedger
from app.seed.demo_seed import run as seed_run
from app.services import finance_control_tower_service as tower

client = TestClient(app)

PATHS = [
    "/api/v1/admin/finance-control-tower/summary",
    "/api/v1/admin/finance-control-tower/exceptions",
    "/api/v1/admin/finance-control-tower/billing-readiness",
    "/api/v1/admin/finance-control-tower/payout-readiness",
]


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _money_tables_snapshot(db) -> dict:
    ledger_n = db.scalar(select(func.count(BillingLedger.id))) or 0
    ledger_sum = float(db.scalar(select(func.coalesce(func.sum(BillingLedger.total_inr), 0))) or 0)
    ci_n = db.scalar(select(func.count(ClientInvoice.id))) or 0
    ci_sum = float(db.scalar(select(func.coalesce(func.sum(ClientInvoice.total_inr), 0))) or 0)
    pay_n = db.scalar(select(func.count(ClientPayment.id))) or 0
    pay_sum = float(db.scalar(select(func.coalesce(func.sum(ClientPayment.amount_inr), 0))) or 0)
    inv_n = db.scalar(select(func.count(Invoice.id))) or 0
    inv_sum = float(db.scalar(select(func.coalesce(func.sum(Invoice.amount_inr), 0))) or 0)
    raw = f"{ledger_n}|{ledger_sum:.2f}|{ci_n}|{ci_sum:.2f}|{pay_n}|{pay_sum:.2f}|{inv_n}|{inv_sum:.2f}"
    return {
        "ledger_n": ledger_n,
        "ledger_sum": ledger_sum,
        "client_invoice_n": ci_n,
        "client_invoice_sum": ci_sum,
        "client_payment_n": pay_n,
        "client_payment_sum": pay_sum,
        "therapist_invoice_n": inv_n,
        "therapist_invoice_sum": inv_sum,
        "checksum": hashlib.sha256(raw.encode()).hexdigest(),
    }


def _assert_no_reconciled(payload) -> None:
    if isinstance(payload, dict):
        if payload.get("confidence") == "RECONCILED":
            raise AssertionError(f"RECONCILED not allowed pre-cutover: {payload}")
        if payload.get("pageConfidence") == "RECONCILED":
            raise AssertionError("pageConfidence RECONCILED not allowed pre-cutover")
        for v in payload.values():
            _assert_no_reconciled(v)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_reconciled(item)


# --- 1–4, 19, 22: permission / flag matrix ---


def test_01_super_admin_can_read_summary():
    r = client.get(PATHS[0], headers=_headers("superadmin@demo.com"), params={"billing_month": "2026-07"})
    assert r.status_code == 200
    body = r.json()
    assert body["readOnly"] is True
    assert "actionQueue" in body
    assert "financeSummary" in body
    assert "contributionMargin" not in body
    assert "contribution_margin" not in body


def test_02_finance_can_read_all_four_gets():
    headers = _headers("finance@demo.com")
    for path in PATHS:
        r = client.get(path, headers=headers, params={"billing_month": "2026-07"})
        assert r.status_code == 200, path


def test_03_case_manager_forbidden_despite_invoice_approve():
    headers = _headers("casemanager@demo.com")
    for path in PATHS:
        r = client.get(path, headers=headers, params={"billing_month": "2026-07"})
        assert r.status_code == 403, path


def test_04_therapist_and_admin_forbidden():
    for email in ("therapist@demo.com", "admin@demo.com"):
        headers = _headers(email)
        r = client.get(PATHS[0], headers=headers, params={"billing_month": "2026-07"})
        assert r.status_code == 403, email


def test_19_enable_billing_false_hides_router(monkeypatch):
    monkeypatch.setattr(settings, "enable_billing", False)
    r = client.get(PATHS[0], headers=_headers("finance@demo.com"), params={"billing_month": "2026-07"})
    assert r.status_code == 404
    monkeypatch.setattr(settings, "enable_billing", True)


def test_22_ledger_writes_false_does_not_block_reads(monkeypatch):
    monkeypatch.setattr(settings, "billing_ledger_writes", False)
    monkeypatch.setattr(settings, "enable_billing", True)
    r = client.get(PATHS[0], headers=_headers("finance@demo.com"), params={"billing_month": "2026-07"})
    assert r.status_code == 200
    monkeypatch.setattr(settings, "billing_ledger_writes", True)


# --- 6–8: before/after zero-write proofs for each GET ---


@pytest.mark.parametrize("path", PATHS, ids=["summary", "exceptions", "billing", "payout"])
def test_06_08_get_zero_write_before_after(path):
    headers = _headers("finance@demo.com")
    db = SessionLocal()
    try:
        before = _money_tables_snapshot(db)
        r = client.get(path, headers=headers, params={"billing_month": "2026-07", "limit": 50})
        assert r.status_code == 200
        db.expire_all()
        after = _money_tables_snapshot(db)
        assert before == after, f"{path} mutated money tables: {before} -> {after}"
    finally:
        db.close()


# --- 12, 14: confidence never RECONCILED pre-cutover ---


def test_12_summary_confidence_never_reconciled_pre_cutover(monkeypatch):
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    r = client.get(PATHS[0], headers=_headers("finance@demo.com"), params={"billing_month": "2026-07"})
    assert r.status_code == 200
    body = r.json()
    assert body["cutoverComplete"] is False
    assert body["provisionalBanner"] is True
    _assert_no_reconciled(body)
    # money_value helper itself downgrades
    mv = tower.money_value(
        value=100,
        confidence="RECONCILED",
        confidence_reason="test",
        record_count=1,
        source_period="2026-07",
    )
    assert mv["confidence"] == "PARTIAL"


def test_14_list_endpoints_confidence_never_reconciled_pre_cutover(monkeypatch):
    monkeypatch.setattr(settings, "finance_cutover_complete", False)
    headers = _headers("finance@demo.com")
    for path in PATHS[1:]:
        r = client.get(path, headers=headers, params={"billing_month": "2026-07"})
        assert r.status_code == 200
        _assert_no_reconciled(r.json())


# --- 20: month filter ---


def test_20_month_filter_propagates():
    headers = _headers("finance@demo.com")
    r = client.get(PATHS[0], headers=headers, params={"billing_month": "2025-01"})
    assert r.status_code == 200
    assert r.json()["billingMonth"] == "2025-01"
    r2 = client.get(PATHS[1], headers=headers, params={"billing_month": "2025-01"})
    assert r2.json()["billingMonth"] == "2025-01"


# --- 23: service has no write helpers / ensure_period_charges ---


def test_23_service_source_is_select_only():
    src = inspect.getsource(tower)
    banned = [
        "ensure_period_charges",
        "db.add(",
        "db.commit(",
        "db.delete(",
        "upsert",
        "SessionLocal().commit",
    ]
    for token in banned:
        assert token not in src, f"write-side token found: {token}"
    # Import graph must not pull period charge writer
    assert "billing_ledger_service" not in src


def test_money_value_omits_value_when_none():
    mv = tower.money_value(
        value=None,
        confidence="INCOMPLETE",
        confidence_reason="missing",
        record_count=0,
        source_period="2026-07",
    )
    assert "value" not in mv
    assert mv["currency"] == "INR"
