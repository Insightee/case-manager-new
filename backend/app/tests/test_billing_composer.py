"""Billing composer queues, preview, line CRUD, and permissions."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

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
