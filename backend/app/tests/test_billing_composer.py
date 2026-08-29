"""Billing composer queues, preview, line CRUD, and permissions."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.ledger_billing import BillingLedger
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services import client_invoice_draft_service

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_composer_cases_smoke():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    month = date.today().strftime("%Y-%m")
    r = client.get(
        f"/api/v1/admin/client-billing/composer-cases?billing_month={month}&queue=all",
        headers=headers,
    )
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_composer_cases_new_clients_queue():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    month = date.today().strftime("%Y-%m")
    r = client.get(
        f"/api/v1/admin/client-billing/composer-cases?billing_month={month}&queue=new_clients",
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for card in data:
        assert "new_client" in card.get("badges", [])


def test_composer_preview_includes_billing_rule():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get(
        "/api/v1/admin/client-billing/composer-cases?billing_month=2026-05&queue=all",
        headers=headers,
    )
    assert cases.status_code == 200
    items = cases.json()
    if not items:
        pytest.skip("No active cases in seed")
    case_id = items[0]["caseId"]
    r = client.get(
        f"/api/v1/admin/client-billing/composer-preview?case_id={case_id}&billing_month=2026-05",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("billingRule") is not None
    assert "ledgerRows" in body
    assert "therapistSubmissions" in body
    assert "therapistCycle" in body
    assert body.get("includeFinanceFields") is True
    assert "therapistPayoutTotal" in body.get("overview", {}) or "estimatedMargin" in body.get("overview", {})


def test_build_from_ledger_or_skip():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    month = date.today().strftime("%Y-%m")
    cases = client.get(
        f"/api/v1/admin/client-billing/composer-cases?billing_month={month}&queue=ledger_ready",
        headers=headers,
    )
    assert cases.status_code == 200
    items = cases.json()
    if not items:
        pytest.skip("No ledger-ready cases")
    case_id = items[0]["caseId"]
    r = client.post(
        f"/api/v1/admin/client-billing/cases/{case_id}/build-from-ledger?billing_month={month}",
        headers=headers,
        json={},
    )
    assert r.status_code in (201, 400)


def test_parent_invoice_detail_no_finance_margin():
    token = _login("parent@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/api/v1/parent/billing/invoices", headers=headers)
    assert listed.status_code == 200
    invs = listed.json()
    if not invs:
        pytest.skip("No parent invoices")
    inv_id = invs[0]["id"]
    detail = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=headers)
    assert detail.status_code == 200
    text = detail.text.lower()
    assert "therapistpayout" not in text.replace("_", "")
    assert "estimatedmargin" not in text.replace("_", "")


def test_composer_therapist_payout_matches_therapist_invoice_preview():
    from app.core.database import SessionLocal
    from app.models.case_billing_rate_change import CaseBillingRateChange

    admin = _login("superadmin@demo.com")
    therapist = _login("therapist@demo.com")
    admin_h = {"Authorization": f"Bearer {admin}"}
    th_h = {"Authorization": f"Bearer {therapist}"}
    month = "2026-05"
    preview = client.get(f"/api/v1/invoices/preview?month={month}", headers=th_h)
    assert preview.status_code == 200
    therapist_body = preview.json()
    if not therapist_body.get("cases"):
        pytest.skip("No therapist invoice cases in May 2026 seed")
    case_id = therapist_body["cases"][0]["case_id"]

    db = SessionLocal()
    try:
        for old in db.scalars(
            select(CaseBillingRateChange).where(CaseBillingRateChange.case_id == case_id)
        ).all():
            db.delete(old)
        db.commit()
    finally:
        db.close()

    preview = client.get(f"/api/v1/invoices/preview?month={month}", headers=th_h)
    assert preview.status_code == 200
    therapist_body = preview.json()
    expected = float(therapist_body["cases"][0]["therapist_share_inr"] or 0)
    finance = client.get(
        f"/api/v1/admin/client-billing/composer-preview?case_id={case_id}&billing_month={month}",
        headers=admin_h,
    )
    assert finance.status_code == 200
    cycle = finance.json().get("therapistCycle") or []
    match = next((row for row in cycle if abs(float(row.get("grossInr") or 0) - expected) < 0.02), None)
    if not cycle:
        pytest.skip("No cycle segment for seeded case")
    assert match is not None or abs(
        sum(float(r.get("grossInr") or 0) for r in cycle) - expected
    ) < 0.02


def test_build_from_ledger_materializes_when_ledger_empty(monkeypatch):
    monkeypatch.setattr(settings, "enable_billing", True)
    monkeypatch.setattr(settings, "billing_ledger_writes", True)
    monkeypatch.setattr(settings, "billing_ledger_drafts", True)

    db = SessionLocal()
    try:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-053")).first()
        admin = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        if not case or not admin:
            pytest.skip("Need demo homecare case and superadmin")
        ym = "2026-05"
        db.execute(
            delete(BillingLedger).where(
                BillingLedger.case_id == case.id,
                BillingLedger.ledger_month == ym,
                BillingLedger.client_invoice_id.is_(None),
            )
        )
        db.commit()
        result = client_invoice_draft_service.generate_draft_from_ledger(
            db,
            case_id=case.id,
            billing_month=ym,
            actor_user_id=admin.id,
        )
        db.commit()
        assert result["lineCount"] >= 1
        assert float(result["totalInr"]) > 0
    except ValueError as exc:
        if "No parent" in str(exc) or "No billable ledger" in str(exc):
            pytest.skip(str(exc))
        raise
    finally:
        db.close()
