from fastapi.testclient import TestClient

from app.main import app
from uuid import uuid4

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _first_case_id(headers: dict[str, str]) -> int:
    res = client.get("/api/v1/cases", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    items = data.get("items", data)
    assert items, "expected seeded cases"
    return int(items[0]["id"])


def _therapist_ids(headers: dict[str, str]) -> list[int]:
    res = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=headers)
    assert res.status_code == 200, res.text
    rows = res.json()
    return [int(r["id"]) for r in rows]


def _ensure_second_therapist(headers: dict[str, str]) -> list[int]:
    ids = _therapist_ids(headers)
    if len(ids) >= 2:
        return ids
    email = f"multi-svc-{uuid4().hex[:8]}@demo.com"
    create = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Multi Service Therapist",
            "role_names": ["THERAPIST"],
            "module_assignments": ["homecare", "shadow_support"],
        },
    )
    assert create.status_code == 201, create.text
    return _therapist_ids(headers)


def test_case_service_lifecycle_and_multi_therapist_assignment():
    admin_headers = _login("superadmin@demo.com")
    case_id = _first_case_id(admin_headers)

    # create a dedicated service line
    create_service = client.post(
        f"/api/v1/cases/{case_id}/services",
        headers=admin_headers,
        json={"service_key": "counselling", "product_module": "homecare"},
    )
    assert create_service.status_code == 201, create_service.text
    service_id = create_service.json()["id"]

    therapist_ids = _ensure_second_therapist(admin_headers)
    assert len(therapist_ids) >= 2
    t1, t2 = therapist_ids[0], therapist_ids[1]

    # assign two different therapists on same service line
    assign_1 = client.post(
        f"/api/v1/cases/{case_id}/services/{service_id}/assignments",
        headers=admin_headers,
        json={"therapist_user_id": t1, "start_date": "2026-01-01"},
    )
    assert assign_1.status_code == 201, assign_1.text
    assign_2 = client.post(
        f"/api/v1/cases/{case_id}/services/{service_id}/assignments",
        headers=admin_headers,
        json={"therapist_user_id": t2, "start_date": "2026-01-01"},
    )
    assert assign_2.status_code == 201, assign_2.text

    # duplicate active therapist assignment for same service line should be rejected
    dup = client.post(
        f"/api/v1/cases/{case_id}/services/{service_id}/assignments",
        headers=admin_headers,
        json={"therapist_user_id": t1, "start_date": "2026-01-02"},
    )
    assert dup.status_code == 400
    assert "already has an active assignment" in dup.text

    # end one assignment and verify service assignment list endpoint
    assignment_id = assign_1.json()["id"]
    end_resp = client.post(
        f"/api/v1/cases/{case_id}/services/{service_id}/assignments/{assignment_id}/end",
        headers=admin_headers,
    )
    assert end_resp.status_code == 200, end_resp.text
    assert end_resp.json()["status"] == "ENDED"

    listing = client.get(
        f"/api/v1/cases/{case_id}/services/{service_id}/assignments",
        headers=admin_headers,
    )
    assert listing.status_code == 200, listing.text
    rows = listing.json()
    assert len(rows) >= 2
    assert any(r["status"] == "ACTIVE" for r in rows)
