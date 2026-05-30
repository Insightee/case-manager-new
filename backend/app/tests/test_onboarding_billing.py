"""Onboarding invoice draft and case billing summary."""
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


def _composer_case_id(headers: dict) -> int | None:
    r = client.get(
        "/api/v1/admin/client-billing/composer-cases?billing_month=2026-05&queue=all",
        headers=headers,
    )
    assert r.status_code == 200
    items = r.json()
    if not items:
        return None
    return items[0]["caseId"]


def test_onboarding_invoice_draft_send_to_queue_only():
    headers = _headers("superadmin@demo.com")
    case_id = _composer_case_id(headers)
    if case_id is None:
        return
    r = client.post(
        f"/api/v1/admin/client-billing/cases/{case_id}/onboarding-invoice-draft",
        headers=headers,
        json={"send_to_queue_only": True},
    )
    assert r.status_code in (200, 201)
    assert r.json().get("queued") is True


def test_case_billing_summary():
    headers = _headers("finance@demo.com")
    case_id = _composer_case_id(headers)
    if case_id is None:
        return
    r = client.get(f"/api/v1/admin/client-billing/cases/{case_id}/billing-summary", headers=headers)
    assert r.status_code == 200
    assert "caseId" in r.json()


def test_finance_overview_summary():
    headers = _headers("finance@demo.com")
    r = client.get("/api/v1/admin/finance-overview/summary", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "queues" in body
    assert "billingMonth" in body
