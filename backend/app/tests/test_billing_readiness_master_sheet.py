"""Billing readiness master sheet + exception rules tests."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.billing_readiness_exception_rule import (
    BillingReadinessExceptionRule,
    BillingReadinessExceptionSeverity,
    BillingReadinessExceptionType,
)
from app.models.case import Case
from app.seed.demo_seed import run as seed_run
from app.services import billing_composer_service, billing_readiness_master_sheet_service as master

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_exception_rules(db) -> None:
    existing = db.scalar(select(BillingReadinessExceptionRule.id).limit(1))
    if existing:
        return
    for exc_type in BillingReadinessExceptionType:
        sev = (
            BillingReadinessExceptionSeverity.BLOCK
            if exc_type
            in (
                BillingReadinessExceptionType.INVOICE_ENGINE_AMOUNT_MISMATCH,
                BillingReadinessExceptionType.STATUS_CONFLICT,
            )
            else BillingReadinessExceptionSeverity.WARN
        )
        tol = 1.0 if exc_type == BillingReadinessExceptionType.INVOICE_ENGINE_AMOUNT_MISMATCH else 0.0
        db.add(
            BillingReadinessExceptionRule(
                exception_type=exc_type,
                tolerance=tol,
                severity=sev,
                active=True,
            )
        )
    db.commit()


def test_master_sheet_engine_amount_matches_composer_preview():
    seed_run()
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        _seed_exception_rules(db)
        case = db.scalar(select(Case).where(Case.billing_type.is_not(None)).limit(1))
        assert case is not None
        ym = "2026-05"
        preview = billing_composer_service.get_composer_preview(db, case_id=case.id, billing_month=ym)
        row = master.compose_master_sheet_row(db, case=case, billing_month=ym)
        assert row["engineAmountInr"] == preview["overview"]["total"]
        assert row["engineSource"] == "billing_composer_service.get_composer_preview"
    finally:
        db.close()


def test_master_sheet_api_no_legacy_invoices_source():
    seed_run()
    headers = _login("finance@demo.com")
    r = client.get(
        "/api/v1/admin/finance-control-tower/billing-readiness-master-sheet?billing_month=2026-05&limit=5",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "client_invoices" in body["sources"]
    assert "billing_ledger" in body["sources"]
    assert "invoices" not in body["sources"]
    assert body["readOnly"] is True
    if body["items"]:
        item = body["items"][0]
        assert "parentName" in item
        assert item["reconciliation"]["raisedInvoiceSource"] == "client_invoices"
        assert item["reconciliation"]["activitySource"] == "billing_ledger_and_sessions"


def test_uninvoiced_case_still_has_session_diff():
    seed_run()
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        _seed_exception_rules(db)
        case = db.scalar(select(Case).where(Case.billing_type.is_not(None)).limit(1))
        assert case is not None
        ym = "2099-01"
        row = master.compose_master_sheet_row(db, case=case, billing_month=ym)
        assert row["reconciliation"]["raisedInvoiceNumber"] is None
        assert row["reconciliation"]["sessionCountDiff"] is not None
        assert row["reconciliation"]["leaveDiff"] is not None
    finally:
        db.close()


def test_master_sheet_reconciliation_uses_insightecase_only():
    """Regression: master sheet must not reference legacy therapist payout invoices table."""
    seed_run()
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        _seed_exception_rules(db)
        case = db.scalar(select(Case).where(Case.billing_type.is_not(None)).limit(1))
        row = master.compose_master_sheet_row(db, case=case, billing_month="2026-05")
        recon = row["reconciliation"]
        assert recon["raisedInvoiceSource"] == "client_invoices"
        assert recon["activitySource"] == "billing_ledger_and_sessions"
        assert "legacy" not in str(row).lower()
    finally:
        db.close()
