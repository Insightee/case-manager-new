"""Parent CM meetings compat route (GET /parent/cm-meetings)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parent_cm_meetings_list_accepts_status_filter():
    headers = _login("parent@demo.com")
    r = client.get("/api/v1/parent/cm-meetings?status=SCHEDULED", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
