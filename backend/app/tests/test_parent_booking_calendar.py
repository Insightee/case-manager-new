"""Parent booking calendar and policy tests."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parent_booking_calendar_endpoint():
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    if not cases:
        return
    case_id = cases[0]["id"]
    therapists = client.get(f"/api/v1/booking/therapists?case_id={case_id}", headers=headers).json()
    if not therapists:
        return
    tid = therapists[0]["therapist_user_id"]
    today = date.today()
    end = today + timedelta(days=7)
    r = client.get(
        f"/api/v1/parent/booking/calendar?case_id={case_id}&therapist_id={tid}"
        f"&from_date={today.isoformat()}&to_date={end.isoformat()}",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "slots" in body
    assert "booking" in body


def test_parent_appointments_include_policy_fields():
    headers = _login("parent@demo.com")
    rows = client.get("/api/v1/parent/appointments", headers=headers).json()
    assert isinstance(rows, list)
    if rows:
        assert "can_cancel" in rows[0]
        assert "can_reschedule" in rows[0]
