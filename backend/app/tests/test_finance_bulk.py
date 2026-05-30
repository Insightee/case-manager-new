from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_bulk_client_invoices_validation():
    headers = _headers("finance@demo.com")
    r = client.post(
        "/api/v1/admin/finance-bulk/client-invoices",
        headers=headers,
        json={"action": "build_from_ledger", "case_ids": [999999], "billing_month": "2099-01"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["failed"]
    assert not body["succeeded"]


def test_review_invoice_requires_in_review():
    headers = _headers("finance@demo.com")
    invoices = client.get("/api/v1/invoices?status=PAID", headers=headers)
    assert invoices.status_code == 200
    paid = invoices.json()
    if not paid:
        return
    inv_id = paid[0]["id"]
    r = client.post(
        f"/api/v1/invoices/{inv_id}/approve",
        headers=headers,
        json={"comment": None},
    )
    assert r.status_code == 400
