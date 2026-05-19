from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import engine
from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def _reset_sqlite_db() -> None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        return
    rel = url.replace("sqlite:///", "")
    db_path = Path(rel) if os.path.isabs(rel) else Path(__file__).resolve().parents[2] / rel.lstrip("./")
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    _reset_sqlite_db()
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_therapist_updates_home_address():
    token = _login("therapist@demo.com")
    r = client.patch(
        "/api/v1/auth/me",
        headers=_headers(token),
        json={
            "home_address_line1": "99 New Home Street",
            "home_city": "Bangalore",
            "home_pincode": "560001",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["home_address"]["address_line1"] == "99 New Home Street"
    assert body["home_address"]["pincode"] == "560001"
    assert "560001" in (body.get("location") or "")


def test_pincode_validation_rejects_invalid():
    token = _login("therapist@demo.com")
    r = client.patch(
        "/api/v1/auth/me",
        headers=_headers(token),
        json={
            "home_address_line1": "1 Test St",
            "home_city": "City",
            "home_pincode": "12ab56",
        },
    )
    assert r.status_code == 400


def test_parent_updates_own_case_service_address():
    parent = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=_headers(parent)).json()
    homecare = next(c for c in cases if c.get("isHomecare"))
    case_id = homecare["id"]

    r = client.patch(
        f"/api/v1/parent/cases/{case_id}/service-address",
        headers=_headers(parent),
        json={
            "address_line1": "22 Updated Lane",
            "city": "Bangalore",
            "pincode": "560103",
        },
    )
    assert r.status_code == 200
    assert "560103" in (r.json().get("serviceAddressSummary") or "")


def test_parent_cannot_update_other_parents_case():
    parent = _login("parent@demo.com")
    r = client.patch(
        "/api/v1/parent/cases/99999/service-address",
        headers=_headers(parent),
        json={"address_line1": "X", "city": "Y", "pincode": "560001"},
    )
    assert r.status_code == 404


def test_therapist_assigned_case_has_maps_url():
    token = _login("therapist@demo.com")
    cases = client.get("/api/v1/cases?assigned=true", headers=_headers(token)).json()
    homecare = next((c for c in cases if c.get("product_module") == "homecare"), None)
    assert homecare is not None
    assert homecare.get("maps_url")
    assert homecare["service_address"]["formatted"]


def test_bookable_cases_include_service_address():
    token = _login("therapist@demo.com")
    rows = client.get("/api/v1/slots/bookable-cases", headers=_headers(token)).json()
    homecare = next((c for c in rows if c.get("is_homecare")), None)
    assert homecare is not None
    assert homecare.get("maps_url")
