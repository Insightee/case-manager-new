"""Billing period snapshot — month close and frozen finance reports."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.ledger_billing import BillableStatus, BillingLedger
from app.seed.demo_seed import run as seed_run
from app.services import finance_payout_preview_service

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str = "superadmin@demo.com") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_close_billing_month_snapshots_payout_preview():
    headers = _login()
    ym = "2026-07"
    db = SessionLocal()
    try:
        live_before = finance_payout_preview_service.payout_preview_rows(db, ym)
    finally:
        db.close()

    r = client.post(
        "/api/v1/admin/finance-reports/close-billing-month",
        headers=headers,
        json={"billing_month": ym, "force": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["billingMonth"] == ym
    assert body["payoutRowCount"] == len(live_before)

    status = client.get(
        f"/api/v1/admin/finance-reports/billing-month-close?billing_month={ym}",
        headers=headers,
    )
    assert status.status_code == 200
    assert status.json()["closed"] is True

    preview = client.get(
        f"/api/v1/admin/finance-reports/therapist-payout-preview?billing_month={ym}",
        headers=headers,
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["dataSource"] == "snapshot"
    assert data["billingMonthClosed"] is True
    assert data["count"] == len(live_before)


def test_closed_month_ignores_case_rate_change():
    headers = _login()
    ym = "2026-07"
    db = SessionLocal()
    try:
        case = db.scalars(select(Case).where(Case.status.isnot(None)).limit(1)).first()
        assert case is not None
        if case.client_rate_per_session_inr:
            case.client_rate_per_session_inr = float(case.client_rate_per_session_inr) + 5000
            db.commit()

        preview = client.get(
            f"/api/v1/admin/finance-reports/therapist-payout-preview?billing_month={ym}",
            headers=headers,
        )
        assert preview.status_code == 200
        assert preview.json()["dataSource"] == "snapshot"
    finally:
        db.close()


def test_ledger_billable_rate_not_overwritten():
    db = SessionLocal()
    try:
        row = db.scalars(
            select(BillingLedger).where(BillingLedger.billable_status == BillableStatus.BILLABLE).limit(1)
        ).first()
        if not row:
            pytest.skip("no billable ledger row in seed")
        original_rate = float(row.rate_inr)
        case = db.get(Case, row.case_id)
        assert case is not None
        if case.client_rate_per_session_inr:
            case.client_rate_per_session_inr = float(case.client_rate_per_session_inr) + 999
        db.commit()

        from app.models.session import Session as TherapySession

        session = db.get(TherapySession, row.session_id) if row.session_id else None
        if session:
            from app.services import billing_ledger_service

            billing_ledger_service.sync_session_status(db, session)
            db.commit()
            db.refresh(row)
            assert float(row.rate_inr) == original_rate
    finally:
        db.close()


def test_close_month_idempotent_without_force():
    headers = _login()
    ym = "2026-07"
    r = client.post(
        "/api/v1/admin/finance-reports/close-billing-month",
        headers=headers,
        json={"billing_month": ym},
    )
    assert r.status_code == 400
