"""Parent therapist leave visibility for session updates."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str = "parent@demo.com") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parent_therapist_leaves_returns_demo_rows():
    headers = _login()
    res = client.get("/api/v1/parent/therapist-leaves", headers=headers, params={"year": 2026, "month": 5})
    assert res.status_code == 200
    rows = res.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    row = rows[0]
    assert row["status"] in ("APPROVED", "PENDING")
    assert row["therapist_name"]
    assert row["child_name"]
    assert "billing_category" not in row
    assert "paid_days" not in row


def test_parent_therapist_leaves_month_filter():
    headers = _login()
    may = client.get("/api/v1/parent/therapist-leaves", headers=headers, params={"year": 2026, "month": 5}).json()
    june = client.get("/api/v1/parent/therapist-leaves", headers=headers, params={"year": 2026, "month": 6}).json()
    assert any(r["reason"] == "Family event" for r in may)
    assert any(r["status"] == "PENDING" for r in june)


def test_parent_therapist_leaves_case_isolation():
    headers = _login()
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    assert cases
    case_id = cases[0]["id"]
    scoped = client.get(
        "/api/v1/parent/therapist-leaves",
        headers=headers,
        params={"case_id": case_id, "year": 2026},
    )
    assert scoped.status_code == 200
    for row in scoped.json():
        assert row["case_id"] == case_id
