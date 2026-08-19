from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_items

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _therapist_case_id(headers: dict) -> int:
    cases = client.get("/api/v1/cases", headers=headers, params={"assigned": True, "page_size": 5})
    assert cases.status_code == 200
    items = api_items(cases.json())
    assert items, "expected assigned case for therapist"
    return items[0]["id"]


def test_monthly_duplicate_draft_returns_conflict():
    headers = _login("therapist@demo.com")
    case_id = _therapist_case_id(headers)
    month = "Test Month 2099-01"

    first = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": month, "category": "CLIENT_MONTHLY"},
    )
    assert first.status_code == 201
    report_id = first.json()["id"]

    second = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": month, "category": "CLIENT_MONTHLY"},
    )
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["existing_report_id"] == report_id
    assert detail["can_delete"] is True

    existing = client.get(
        "/api/v1/reports/monthly/existing",
        headers=headers,
        params={"case_id": case_id, "month": month, "category": "CLIENT_MONTHLY"},
    )
    assert existing.status_code == 200
    body = existing.json()
    assert body["exists"] is True
    assert body["report_id"] == report_id


def test_delete_monthly_draft_only():
    headers = _login("therapist@demo.com")
    case_id = _therapist_case_id(headers)
    month = "Test Month 2099-02"

    created = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": month, "category": "CLIENT_MONTHLY"},
    )
    assert created.status_code == 201
    report_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/reports/monthly/{report_id}", headers=headers)
    assert deleted.status_code == 204

    refetch = client.get(f"/api/v1/reports/monthly/{report_id}", headers=headers)
    assert refetch.status_code == 404

    recreate = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": month, "category": "CLIENT_MONTHLY"},
    )
    assert recreate.status_code == 201
