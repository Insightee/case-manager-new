"""Parent next-open-slot and meeting request APIs."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parent_next_open_slot_shape():
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    if not cases:
        return
    case_id = cases[0]["id"]
    therapists = client.get(f"/api/v1/booking/therapists?case_id={case_id}", headers=headers).json()
    if not therapists:
        return
    tid = therapists[0]["therapist_user_id"]
    r = client.get(
        f"/api/v1/parent/booking/next-open-slot?case_id={case_id}&therapist_id={tid}&horizon_days=7",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("horizon_days") == 7
    assert "next_slot" in body


def test_parent_meeting_request_and_therapist_list():
    parent_headers = _login("parent@demo.com")
    therapist_headers = _login("therapist@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=parent_headers).json()
    if not cases:
        return
    case_id = cases[0]["id"]
    therapists = client.get(f"/api/v1/booking/therapists?case_id={case_id}", headers=parent_headers).json()
    if not therapists:
        return
    tid = therapists[0]["therapist_user_id"]
    preferred = date.today() + timedelta(days=14)
    r = client.post(
        "/api/v1/parent/booking/meeting-requests",
        headers=parent_headers,
        json={
            "case_id": case_id,
            "therapist_user_id": tid,
            "requested_date": preferred.isoformat(),
            "note": "Afternoon if possible",
        },
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["status"] == "PENDING"
    assert created["requested_date"] == preferred.isoformat()

    listed = client.get("/api/v1/scheduling/parent-meeting-requests", headers=therapist_headers).json()
    assert isinstance(listed, list)
    assert any(row["id"] == created["id"] for row in listed)


def test_parent_meeting_request_rejects_unassigned_therapist():
    parent_headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=parent_headers).json()
    if not cases:
        return
    case_id = cases[0]["id"]
    therapists = client.get(f"/api/v1/booking/therapists?case_id={case_id}", headers=parent_headers).json()
    if not therapists:
        return
    assigned_tid = therapists[0]["therapist_user_id"]
    wrong_tid = assigned_tid + 999_999
    preferred = date.today() + timedelta(days=21)
    r = client.post(
        "/api/v1/parent/booking/meeting-requests",
        headers=parent_headers,
        json={
            "case_id": case_id,
            "therapist_user_id": wrong_tid,
            "requested_date": preferred.isoformat(),
        },
    )
    assert r.status_code == 400, r.text
    assert "not assigned" in r.json().get("detail", "").lower()
