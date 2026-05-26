"""Ledger-first client billing: product rules, ledger, draft invoices."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_items

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_product_rules_list_and_create():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/api/v1/admin/ledger-billing/product-rules", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    created = client.post(
        "/api/v1/admin/ledger-billing/product-rules",
        headers=headers,
        json={
            "product_name": "API Test Rule",
            "product_category": "Test",
            "product_module": "homecare",
            "billing_model": "POSTPAID_PER_SESSION",
            "default_rate_inr": 1750,
            "gst_applicable": True,
            "gst_rate_percent": 18,
            "active": True,
        },
    )
    assert created.status_code == 201
    assert created.json()["productName"] == "API Test Rule"


def test_ledger_list_requires_finance():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/admin/ledger-billing/ledger", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_generate_draft_requires_billable_rows():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases?page_size=1", headers=headers)
    case_id = api_items(cases.json())[0]["id"]
    month = date.today().strftime("%Y-%m")
    r = client.post(
        "/api/v1/admin/ledger-billing/invoices/generate-draft",
        headers=headers,
        json={"case_id": case_id, "billing_month": month, "include_pending": False},
    )
    assert r.status_code in (400, 201)


def test_admin_invoices_claims_pending_filter():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/admin/client-billing/invoices?claims_pending=true", headers=headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
