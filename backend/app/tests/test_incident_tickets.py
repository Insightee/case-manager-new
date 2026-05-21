from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.incident import Incident, IncidentStatus
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str = "therapist@demo.com") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_payload(**overrides):
    base = {
        "case_id": None,
        "primary_category": "LEGAL_POSH_CPP_POCSO",
        "subcategory": "pocso_concern",
        "what_happened": "Test incident description for routing.",
        "service_type": "homecare",
        "location": "home",
        "child_safe": "yes",
        "parent_informed": "na",
    }
    base.update(overrides)
    return base


def test_create_incident_routes_legal_to_hr_critical():
    token = _login()
    r = client.post(
        "/api/v1/incidents",
        headers=_headers(token),
        json=_create_payload(),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["ticket_code"].startswith("INC-")
    assert data["primary_owner_role"] == "HR"
    assert data["priority"] == "CRITICAL"
    assert data["status"] == "REPORTED"
    assert "confirmation" in data


def test_therapist_conduct_routes_to_hr():
    token = _login()
    r = client.post(
        "/api/v1/incidents",
        headers=_headers(token),
        json=_create_payload(
            primary_category="THERAPIST_PARENT_CONDUCT",
            subcategory="therapist_late_noshow",
            priority=None,
        ),
    )
    assert r.status_code == 201
    assert r.json()["primary_owner_role"] == "HR"


def test_close_requires_action_note():
    token = _login("superadmin@demo.com")
    headers = _headers(token)
    created = client.post(
        "/api/v1/incidents",
        headers=headers,
        json=_create_payload(
            primary_category="SESSION_CLASSROOM_PROGRAM",
            subcategory="session_disrupted",
        ),
    ).json()

    bad = client.patch(
        f"/api/v1/incidents/{created['id']}",
        headers=headers,
        json={"status": "CLOSED"},
    )
    assert bad.status_code == 400
    assert "action" in bad.json()["detail"].lower()

    ok = client.patch(
        f"/api/v1/incidents/{created['id']}",
        headers=headers,
        json={"status": "CLOSED", "action_taken_note": "Reviewed and documented."},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "CLOSED"


def test_incidents_meta_endpoint():
    token = _login()
    r = client.get("/api/v1/incidents/meta", headers=_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert len(data["primary_categories"]) == 7
    assert "CHILD_SAFETY_MEDICAL" in data["subcategories_by_category"]


def test_attachment_upload():
    token = _login()
    headers = _headers(token)
    created = client.post(
        "/api/v1/incidents",
        headers=headers,
        json=_create_payload(
            primary_category="BEHAVIOUR_EMOTIONAL",
            subcategory="aggression",
        ),
    ).json()

    files = {"files": ("note.txt", b"incident attachment content", "text/plain")}
    up = client.post(
        f"/api/v1/incidents/{created['id']}/attachments",
        headers=headers,
        files=files,
    )
    assert up.status_code == 201, up.text
    assert len(up.json()["attachments"]) == 1

    detail = client.get(f"/api/v1/incidents/{created['id']}", headers=headers).json()
    assert detail["attachments"][0]["file_name"] == "note.txt"
