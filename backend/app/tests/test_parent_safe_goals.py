"""Parent-safe goals field allowlist."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.parent_safe_goals_service import PARENT_GOAL_KEYS

client = TestClient(app)

FORBIDDEN = frozenset(
    {
        "review_status",
        "review_note",
        "evidence_count",
        "lifecycle_status",
        "strategy_feedback",
        "created_by_user_id",
        "raw_ai_output",
        "clinical_confidence",
    }
)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _parent_case_id(headers: dict[str, str]) -> int:
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    assert cases
    return cases[0]["id"]


def test_parent_safe_goals_allowlist():
    headers = _login("parent@demo.com")
    case_id = _parent_case_id(headers)
    r = client.get(f"/api/v1/parent/cases/{case_id}/parent-safe-goals", headers=headers)
    assert r.status_code == 200, r.text
    for item in r.json().get("items") or []:
        for key in item:
            assert key in PARENT_GOAL_KEYS, f"Unexpected parent field: {key}"
            assert key not in FORBIDDEN


def test_therapist_cannot_access_parent_safe_goals_route():
    headers = _login("therapist@demo.com")
    case_id = _parent_case_id(_login("parent@demo.com"))
    r = client.get(f"/api/v1/parent/cases/{case_id}/parent-safe-goals", headers=headers)
    assert r.status_code == 403
