"""GET /api/v1/sessions/{id} for therapist deep links."""

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


def test_therapist_can_get_session_by_id_for_deep_link():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    upcoming = client.get("/api/v1/sessions/upcoming?days=14", headers=headers)
    assert upcoming.status_code == 200
    rows = upcoming.json()
    assert rows, "demo seed should include upcoming sessions"
    sid = rows[0]["id"]
    got = client.get(f"/api/v1/sessions/{sid}", headers=headers)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["id"] == sid
    assert body["status"] == "SCHEDULED"
