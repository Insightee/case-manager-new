from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def _login(email: str = "parent@demo.com") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_parent_can_create_incident():
    seed_run()
    token = _login()
    cases = client.get("/api/v1/parent/cases", headers=_headers(token)).json()
    assert cases, "parent needs at least one case"
    case_id = cases[0]["id"]
    r = client.post(
        "/api/v1/parent/incidents",
        headers=_headers(token),
        json={
            "case_id": case_id,
            "primary_category": "CHILD_SAFETY_MEDICAL",
            "subcategory": "injury_fall",
            "what_happened": "Parent reported a fall during session with adequate detail.",
            "priority": "URGENT",
            "service_type": "homecare",
            "incident_at": "2026-05-28T10:00:00+00:00",
            "location": "school",
            "child_safe": "yes",
            "parent_informed": "yes",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["ticket_code"].startswith("INC-")
    assert data.get("confirmation")

    listed = client.get("/api/v1/parent/incidents", headers=_headers(token))
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert any(row["ticket_code"] == data["ticket_code"] for row in rows)
    assert rows[0]["status"] == "REPORTED"
