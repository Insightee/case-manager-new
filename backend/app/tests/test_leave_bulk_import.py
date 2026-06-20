from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.main import app
from app.models.user import User
from app.services import leave_policy_service as policy
from app.services.leave_bulk_import_service import (
    BULK_LEAVE_IMPORT_YEAR,
    apply_bulk_leave_import,
    compute_usage_from_leaves_used,
    preview_bulk_leave_import,
)
from app.services.therapist_profile_service import get_or_create_profile
from app.seed.demo_seed import run as seed_run
from app.tests.test_leave_policy import _ensure_therapist_profile, _headers, _login

client = TestClient(app)


def _reset_sqlite_db() -> None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        return
    rel = url.replace("sqlite:///", "")
    db_path = Path(rel) if os.path.isabs(rel) else Path(__file__).resolve().parents[2] / rel.lstrip("./")
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        p = Path(f"{db_path}{suffix}")
        if p.exists():
            p.unlink()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    _reset_sqlite_db()
    seed_run()


def test_compute_usage_nov_2025_start_seven_used():
    usage = compute_usage_from_leaves_used(
        date(2025, 11, 1),
        7,
        year=2026,
        as_of=date(2026, 6, 18),
    )
    assert usage["credits_earned"] == 6
    assert usage["paid_used"] == 6
    assert usage["unpaid_over_limit"] == 1
    assert usage["leave_credit_pending"] == 0


def test_preview_bulk_leave_import():
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        user.external_employee_id = "EMP-THERAPIST-1"
        db.commit()

        csv_text = "external_employee_id,start_date,leaves_used\nEMP-THERAPIST-1,2025-11-01,7\n"
        preview = preview_bulk_leave_import(db, csv_text, year=BULK_LEAVE_IMPORT_YEAR)
        assert preview["ok_rows"] == 1
        row = preview["rows"][0]
        assert row["status"] == "ok"
        assert row["paid_used"] == 6
        assert row["unpaid_over_limit"] == 1
    finally:
        db.close()


def test_apply_bulk_leave_import_updates_snapshot():
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        user.external_employee_id = "EMP-APPLY-1"
        db.commit()

        csv_text = "external_employee_id,start_date,leaves_used\nEMP-APPLY-1,2025-11-01,7\n"
        result = apply_bulk_leave_import(
            db,
            csv_text,
            year=BULK_LEAVE_IMPORT_YEAR,
            actor_user_id=user.id,
        )
        db.commit()
        assert result["updated"] == 1

        profile = get_or_create_profile(db, user.id)
        assert profile.employment_start_date == date(2025, 11, 1)
        snapshot = profile.leave_year_snapshots[str(BULK_LEAVE_IMPORT_YEAR)]
        assert snapshot["paid_used"] == 6
        assert snapshot["unpaid_over_limit"] == 1

        bal = policy.get_leave_balance(db, user, year=BULK_LEAVE_IMPORT_YEAR)
        assert bal["usage_snapshot_applied"] is True
        assert bal["paid_leaves_taken"] == 6
        assert bal["unpaid_over_limit"] == 1
        assert bal["leave_credit_pending"] == 0
    finally:
        db.close()


def test_bulk_leave_api_preview_and_apply():
    hr = _login("hr@demo.com")
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        user.external_employee_id = "EMP-API-1"
        _ensure_therapist_profile(db, user.id, employment_start=date(2020, 1, 1))
        db.commit()
    finally:
        db.close()

    csv_text = "external_employee_id,start_date,leaves_used\nEMP-API-1,2025-11-01,4\n"
    preview = client.post(
        "/api/v1/hr/leave/bulk/preview",
        headers=_headers(hr),
        json={"csv_text": csv_text, "year": 2026},
    )
    assert preview.status_code == 200
    assert preview.json()["ok_rows"] == 1

    apply = client.post(
        "/api/v1/hr/leave/bulk/apply",
        headers=_headers(hr),
        json={"csv_text": csv_text, "year": 2026},
    )
    assert apply.status_code == 200
    assert apply.json()["updated"] == 1

    therapist = _login("therapist@demo.com")
    bal = client.get("/api/v1/leave/balance?year=2026", headers=_headers(therapist))
    assert bal.status_code == 200
    data = bal.json()
    assert data["paid_leaves_taken"] == 4
    assert data["usage_snapshot_applied"] is True
