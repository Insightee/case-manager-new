from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    from app.seed.demo_seed import run as seed_run

    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _therapist_scheduled_session(headers: dict) -> int:
    r = client.get("/api/v1/sessions?assigned=true&page_size=50", headers=headers)
    assert r.status_code == 200
    items = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
    for s in items:
        if s.get("status") == "SCHEDULED":
            return int(s["id"])
    today = date.today().isoformat()
    cases = client.get("/api/v1/cases?assigned=true&page_size=1", headers=headers).json()
    case_items = cases.get("items", cases) if isinstance(cases, dict) else cases
    case_id = int(case_items[0]["id"])
    created = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "case_id": case_id,
            "therapist_user_id": 0,
            "scheduled_date": today,
            "start_time": "10:00",
            "end_time": "11:00",
            "mode": "HOME",
            "status": "SCHEDULED",
        },
    )
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


def test_child_absent_parent_approve_flow():
    therapist_headers = _login("therapist@demo.com")
    session_id = _therapist_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Unwell"},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["status"] == "PENDING_APPROVAL"
    assert body["absence_type"] == "CLIENT_ABSENT"

    parent_headers = _login("parent@demo.com")
    inbox = client.get("/api/v1/parent/absence-requests", headers=parent_headers)
    assert inbox.status_code == 200
    ids = {item["id"] for item in inbox.json().get("items", [])}
    assert body["id"] in ids

    approve = client.post(
        f"/api/v1/sessions/absence/{body['id']}/approve",
        headers=parent_headers,
        json={},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"

    sessions = client.get("/api/v1/sessions?page_size=100", headers=therapist_headers)
    assert sessions.status_code == 200
    items = sessions.json().get("items", sessions.json()) if isinstance(sessions.json(), dict) else sessions.json()
    row = next((s for s in items if s["id"] == session_id), None)
    assert row is not None
    assert row["status"] in ("CLIENT_ABSENT", "CANCELLED")


def test_therapist_leave_admin_approve():
    therapist_headers = _login("therapist@demo.com")
    session_id = _therapist_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={
            "absence_type": "THERAPIST_LEAVE",
            "leave_billing_category": "UNPAID",
            "reason": "Personal",
        },
    )
    assert create.status_code == 201, create.text
    req_id = create.json()["id"]

    admin_headers = _login("superadmin@demo.com")
    pending = client.get("/api/v1/sessions/absence/pending", headers=admin_headers)
    assert pending.status_code == 200
    assert req_id in {i["id"] for i in pending.json().get("items", [])}

    approve = client.post(
        f"/api/v1/sessions/absence/{req_id}/approve",
        headers=admin_headers,
        json={"review_note": "Approved"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"
