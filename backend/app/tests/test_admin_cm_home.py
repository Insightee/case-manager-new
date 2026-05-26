"""Case Manager dedicated home API."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cm_home_for_case_manager():
    r = client.get("/api/v1/admin/cm/home", headers=_login("casemanager@demo.com"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "CASE_MANAGER"
    assert body["landing_route"] == "/admin/cm"
    assert "caseload_summary" in body
    assert "caseload" in body
    assert "sections" in body
    assert isinstance(body["quick_actions"], list)


def test_cm_home_forbidden_for_finance():
    r = client.get("/api/v1/admin/cm/home", headers=_login("finance@demo.com"))
    assert r.status_code == 403
