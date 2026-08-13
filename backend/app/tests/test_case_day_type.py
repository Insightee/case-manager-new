"""Tests for case half-day / full-day type."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_child(admin_headers: dict) -> int:
    suffix = uuid.uuid4().hex[:8]
    fam = client.post(
        "/api/v1/admin/families",
        headers=admin_headers,
        json={
            "parent_email": f"daytype-parent-{suffix}@demo.com",
            "parent_full_name": "Day Type Parent",
            "child": {"first_name": "Day", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    return fam.json()["childId"]


def _allot_shadow(admin_headers: dict, child_id: int, therapist_id: int, *, day_type: str | None = None):
    payload = {
        "child_id": child_id,
        "service_type": "Shadow support",
        "product_module": "shadow_support",
        "billing_type": "PER_SESSION",
        "compensation_mode": "PERCENTAGE",
        "client_billing_mode": "POSTPAID",
        "client_rate_per_session_inr": 1200,
        "pay_share_amount_inr": 720,
        "therapist_user_id": therapist_id,
    }
    if day_type:
        payload["day_type"] = day_type
    return client.post("/api/v1/admin/cases/allot", headers=admin_headers, json=payload)


def test_allot_shadow_requires_day_type():
    admin_headers = _login("superadmin@demo.com")
    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=shadow_support&approved_only=false",
        headers=admin_headers,
    )
    therapist_id = therapists.json()[0]["therapist_user_id"]
    child_id = _create_child(admin_headers)

    missing = _allot_shadow(admin_headers, child_id, therapist_id)
    assert missing.status_code == 400
    assert "half day" in missing.json()["detail"].lower()

    ok = _allot_shadow(admin_headers, child_id, therapist_id, day_type="HALF_DAY")
    assert ok.status_code == 201
    assert ok.json()["case"]["day_type"] == "HALF_DAY"


def test_update_day_type_first_set_no_reason():
    admin_headers = _login("superadmin@demo.com")
    cases = client.get("/api/v1/cases?product_module=shadow_support&page_size=50", headers=admin_headers)
    assert cases.status_code == 200
    case = next((c for c in cases.json()["items"] if not c.get("day_type")), None)
    assert case is not None, "Expected a legacy shadow case without day_type"
    case_id = case["id"]

    res = client.patch(
        f"/api/v1/cases/{case_id}/day-type",
        headers=admin_headers,
        json={"day_type": "FULL_DAY"},
    )
    assert res.status_code == 200
    assert res.json()["day_type"] == "FULL_DAY"


def test_update_day_type_change_requires_reason_and_timeline():
    admin_headers = _login("superadmin@demo.com")
    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=shadow_support&approved_only=false",
        headers=admin_headers,
    )
    therapist_id = therapists.json()[0]["therapist_user_id"]
    child_id = _create_child(admin_headers)
    created = _allot_shadow(admin_headers, child_id, therapist_id, day_type="HALF_DAY")
    assert created.status_code == 201
    case_id = created.json()["case"]["id"]

    blocked = client.patch(
        f"/api/v1/cases/{case_id}/day-type",
        headers=admin_headers,
        json={"day_type": "FULL_DAY"},
    )
    assert blocked.status_code == 400

    ok = client.patch(
        f"/api/v1/cases/{case_id}/day-type",
        headers=admin_headers,
        json={"day_type": "FULL_DAY", "reason": "Student moved to full-day classes"},
    )
    assert ok.status_code == 200
    assert ok.json()["day_type"] == "FULL_DAY"

    timeline = client.get(f"/api/v1/admin/cases/{case_id}/timeline", headers=admin_headers)
    assert timeline.status_code == 200
    actions = [item.get("action") for item in timeline.json()["items"]]
    assert "update_day_type" in actions


def test_homecare_rejects_day_type():
    admin_headers = _login("superadmin@demo.com")
    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=admin_headers,
    )
    therapist_id = therapists.json()[0]["therapist_user_id"]
    child_id = _create_child(admin_headers)
    created = client.post(
        "/api/v1/admin/cases/allot",
        headers=admin_headers,
        json={
            "child_id": child_id,
            "service_type": "Homecare",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_amount_inr": 720,
            "therapist_user_id": therapist_id,
        },
    )
    assert created.status_code == 201
    case_id = created.json()["case"]["id"]

    res = client.patch(
        f"/api/v1/cases/{case_id}/day-type",
        headers=admin_headers,
        json={"day_type": "HALF_DAY"},
    )
    assert res.status_code == 400
