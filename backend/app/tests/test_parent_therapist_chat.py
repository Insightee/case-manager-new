"""Parent therapist chat thread (support ticket backend)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parent_therapist_chat_opens_and_reuses_thread():
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    if not cases:
        return
    case_id = cases[0]["id"]
    r1 = client.get(f"/api/v1/parent/therapist-chat?case_id={case_id}", headers=headers)
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["subject"] == "Therapist chat"
    assert body1["topic"] == "OTHER"
    assert body1.get("assigned_to_name")

    r2 = client.get(f"/api/v1/parent/therapist-chat?case_id={case_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == body1["id"]
