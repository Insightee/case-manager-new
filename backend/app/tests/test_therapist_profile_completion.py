from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_therapist_me_includes_profile_completion():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert "profile_completion" in body
    pc = body["profile_completion"]
    assert pc is not None
    assert "percent" in pc
    assert "complete" in pc
    assert "missing_fields" in pc
    assert isinstance(pc["missing_fields"], list)
    assert 0 <= pc["percent"] <= 100
    assert "total_steps" in pc
    assert "completed_steps" in pc
    assert pc["completed_steps"] + len(pc["missing_fields"]) == pc["total_steps"]
    assert "needs_nudge" in pc


def test_needs_nudge_false_after_submit():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    client.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={
            "phone": "9876543210",
            "home_address_line1": "12 MG Road",
            "home_city": "Bengaluru",
            "home_pincode": "560001",
        },
    )
    submit = client.post(
        "/api/v1/therapist/profile/submit",
        headers=headers,
        json={
            "display_name": "Nudge Check",
            "services_offered": ["homecare"],
            "professional_qualification_entries": [{"kind": "degree", "title": "B.Ed", "year": 2018}],
        },
    )
    assert submit.status_code == 200
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["profile_completion"]["needs_nudge"] is False


def test_admin_me_has_no_profile_completion_block():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json().get("profile_completion") is None
