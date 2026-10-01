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


def test_admin_me_has_no_profile_completion_block():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json().get("profile_completion") is None
