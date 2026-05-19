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


def test_late_session_pending_excluded_from_net_until_approved():
    therapist = _login("therapist@demo.com")
    admin = _login("superadmin@demo.com")
    th = _headers(therapist)

    preview = client.get("/api/v1/invoices/preview?month=2026-05", headers=th)
    assert preview.status_code == 200
    body = preview.json()
    net_before = body["net_amount_inr"]
    case_id = body["cases"][0]["case_id"]

    create = client.post(
        "/api/v1/invoices/late-sessions",
        headers=th,
        json={
            "case_id": case_id,
            "month": "2026-05",
            "session_date": "2026-05-20",
            "start_time": "14:00:00",
            "end_time": "15:00:00",
            "attendance_status": "present",
            "activities_done": "Make-up session",
            "late_reason": "Forgot to log after home visit",
        },
    )
    assert create.status_code == 201
    log_id = create.json()["daily_log_id"]
    assert create.json()["preview_line"]["flags"]["pending_approval"] is True

    pending_preview = client.get("/api/v1/invoices/preview?month=2026-05", headers=th).json()
    assert pending_preview["pending_late_count"] >= 1
    assert pending_preview["pending_late_inr"] > 0
    assert pending_preview["net_amount_inr"] == net_before

    pending_case = next(c for c in pending_preview["cases"] if c["case_id"] == case_id)
    assert len(pending_case.get("pending_late_lines", [])) >= 1

    approve = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=_headers(admin))
    assert approve.status_code == 200

    approved_preview = client.get("/api/v1/invoices/preview?month=2026-05", headers=th).json()
    assert approved_preview["net_amount_inr"] > net_before
    assert approved_preview["total_sessions"] == body["total_sessions"] + 1


def test_late_session_delete_before_approval():
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)

    preview = client.get("/api/v1/invoices/preview?month=2026-05", headers=th).json()
    case_id = preview["cases"][0]["case_id"]

    create = client.post(
        "/api/v1/invoices/late-sessions",
        headers=th,
        json={
            "case_id": case_id,
            "month": "2026-05",
            "session_date": "2026-05-21",
            "start_time": "16:00:00",
            "end_time": "17:00:00",
            "attendance_status": "present",
            "late_reason": "Added by mistake during invoice review",
        },
    )
    assert create.status_code == 201
    session_id = create.json()["session_id"]

    delete = client.delete(f"/api/v1/invoices/late-sessions/{session_id}", headers=th)
    assert delete.status_code == 204

    after = client.get("/api/v1/invoices/preview?month=2026-05", headers=th).json()
    all_pending = [ln for c in after["cases"] for ln in c.get("pending_late_lines", [])]
    assert not any(ln.get("session_id") == session_id for ln in all_pending)
