"""Feature flag API gates."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_clinical_brain_gated_when_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_clinical_brain", False)
    headers = _login("superadmin@demo.com")
    r = client.get("/api/v1/clinical-brain/review-queue", headers=headers)
    assert r.status_code == 404


def test_therapist_home_works_when_reports_disabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "enable_reports", False)
    monkeypatch.setattr(settings, "enable_clinical_brain", False)
    headers = _login("therapist@demo.com")
    r = client.get("/api/v1/therapist/home", headers=headers)
    assert r.status_code == 200
    assert "cases_board" in r.json()
