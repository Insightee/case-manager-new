"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_TEST_DB = _BACKEND_ROOT / f"test_ci_{os.getpid()}.db"

# Must run before test modules import app.main (engine binds to DATABASE_URL).
os.environ.setdefault("STORAGE_PROVIDER", "local")
os.environ.setdefault("APP_ENV", "test")
os.environ["ENABLE_BILLING"] = "true"
os.environ["BILLING_LEDGER_WRITES"] = "true"
os.environ["ENABLE_CLINICAL_REPORTS_ENGINE"] = "true"
os.environ["INTEGRATION_API_ENABLED"] = "true"
os.environ["MCP_ENABLED"] = "true"

_MIGRATION_PROOF_CI = os.environ.get("MIGRATION_PROOF_REQUIRED", "").lower() in ("1", "true", "yes")
if not _MIGRATION_PROOF_CI:
    os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

_BOOTSTRAP_DONE = False


def _bootstrap_test_database() -> None:
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    env = {**os.environ, "PYTHONPATH": f"{_BACKEND_ROOT}:{_BACKEND_ROOT / 'alembic'}"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_ROOT,
        env=env,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-c", "from app.core.database import ensure_sqlite_schema_patches; ensure_sqlite_schema_patches()"],
        cwd=_BACKEND_ROOT,
        env=env,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "app.seed.demo_seed"],
        cwd=_BACKEND_ROOT,
        env=env,
        check=True,
    )
    _BOOTSTRAP_DONE = True


if not _MIGRATION_PROOF_CI:
    _bootstrap_test_database()


def api_items(data):
    """Unwrap paginated API responses for assertions."""
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data


def api_first_case_id(client, headers: dict, *, page_size: int = 1) -> int:
    """First case visible to the authenticated user (team-scoped for CMs)."""
    res = client.get(f"/api/v1/cases?page_size={page_size}", headers=headers)
    assert res.status_code == 200, res.text
    items = api_items(res.json())
    assert items, "Expected at least one visible case"
    return int(items[0]["id"])


def login_headers(client, email: str, password: str = "demo123") -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def cm_headers_for_case(client, case_id: int, password: str = "demo123") -> dict[str, str]:
    """Auth headers for the case manager assigned to ``case_id``."""
    from app.core.database import SessionLocal
    from app.models.case import Case
    from app.models.user import User

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None and case.case_manager_user_id is not None
        cm = db.get(User, case.case_manager_user_id)
        assert cm is not None
        email = cm.email
    finally:
        db.close()
    return login_headers(client, email, password=password)


def future_meeting_date(days_ahead: int = 14) -> str:
    """ISO date for tests that hardcode 11:00 without reading the host calendar.

    Weekends are open by default. This helper still prefers a weekday so
    hardcoded 11:00 stays valid if a fixture later closed Sat/Sun.
    Use ``first_meeting_slot`` to accept a Saturday CM slot when it is open.
    """
    from datetime import date, timedelta

    target = date.today() + timedelta(days=days_ahead)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    return target.isoformat()


def past_meeting_date(days_ago: int = 1) -> str:
    """ISO date in the past for meeting completion tests."""
    from datetime import date, timedelta

    return (date.today() - timedelta(days=days_ago)).isoformat()


def today_meeting_date() -> str:
    """Today's date in IST for same-day meeting tests."""
    from app.core.timezone import today_ist

    return today_ist().isoformat()


def first_meeting_slot(
    client,
    headers: dict[str, str],
    user_ids: list[int],
    *,
    days_ahead: int = 14,
    duration_minutes: int = 30,
    slot_index: int = 0,
) -> tuple[str, str]:
    """Return a bookable (date, time) from the host calendar, including Saturday if open."""
    from datetime import date, timedelta

    start = date.today() + timedelta(days=days_ahead)
    end = start + timedelta(days=6)
    res = client.get(
        "/api/v1/calendar/availability",
        headers=headers,
        params={
            "user_ids": ",".join(str(uid) for uid in user_ids),
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "duration_minutes": duration_minutes,
        },
    )
    assert res.status_code == 200, res.text
    slots = res.json().get("slots", [])
    assert slots, f"Expected availability slots for users {user_ids} between {start} and {end}"
    slot = slots[min(slot_index, len(slots) - 1)]
    return slot["date"], f"{slot['time']}:00"


def meeting_slot_near_minutes_ahead(
    client,
    headers: dict[str, str],
    user_ids: list[int],
    *,
    minutes_ahead: int,
    duration_minutes: int = 30,
) -> dict[str, object]:
    """Build a meeting payload scheduled near ``minutes_ahead`` on a valid slot."""
    from datetime import date, datetime, time, timedelta

    from app.core.timezone import IST, now_ist

    now = now_ist()
    if minutes_ahead <= 60:
        window_start = now + timedelta(minutes=25)
        window_end = now + timedelta(minutes=59)
        day_offsets = range(2)
    elif minutes_ahead <= 70:
        window_start = now + timedelta(minutes=55)
        window_end = now + timedelta(minutes=70)
        day_offsets = range(2)
    else:
        target = now + timedelta(minutes=minutes_ahead)
        if target.minute % 30:
            target = target + timedelta(minutes=30 - (target.minute % 30))
        target = target.replace(second=0, microsecond=0)
        while target.weekday() >= 5:
            target = (target + timedelta(days=1)).replace(hour=10, minute=0)
        window_start = target
        window_end = target
        day_offsets = [0]

    for day_offset in day_offsets:
        day = (now + timedelta(days=day_offset)).date()
        res = client.get(
            "/api/v1/calendar/availability",
            headers=headers,
            params={
                "user_ids": ",".join(str(uid) for uid in user_ids),
                "date_from": day.isoformat(),
                "date_to": day.isoformat(),
                "duration_minutes": duration_minutes,
            },
        )
        assert res.status_code == 200, res.text
        for slot in res.json().get("slots", []):
            start = datetime.combine(
                date.fromisoformat(slot["date"]),
                time.fromisoformat(f"{slot['time']}:00"),
                tzinfo=IST,
            )
            if window_start == window_end or window_start <= start <= window_end:
                return {
                    "scheduled_date": slot["date"],
                    "scheduled_time": f"{slot['time']}:00",
                    "duration_minutes": duration_minutes,
                    "meeting_type": "PARENT_MEETING",
                }

    raise AssertionError(
        f"No availability slot found between {window_start.isoformat()} and {window_end.isoformat()}"
    )


def isolated_homecare_case(db):
    """Dedicated PER_SESSION homecare case for billing tests (avoids mutating seed cases)."""
    from sqlalchemy import select

    from app.models.case import BillingType, Case, CaseStatus, CompensationMode
    from app.models.child import Child

    child = db.scalars(select(Child).limit(1)).first()
    assert child is not None
    case = Case(
        case_code=f"ISO-HC-{uuid.uuid4().hex[:8]}",
        child_id=child.id,
        service_type="homecare",
        product_module="homecare",
        status=CaseStatus.ACTIVE,
        billing_type=BillingType.PER_SESSION,
        compensation_mode=CompensationMode.PERCENTAGE,
        client_rate_per_session_inr=1500,
        therapist_fixed_pay_inr=1200,
        pay_share_amount_inr=1200,
    )
    db.add(case)
    db.flush()
    return case


def restore_demo_seed_case_modules(db) -> None:
    """Reset canonical demo case product lines after tests that repurpose case rows."""
    from sqlalchemy import select

    from app.models.case import Case

    for code, module, service in (
        ("IC-2026-041", "shadow_support", "Shadow Support"),
        ("IC-2026-053", "homecare", "Homecare"),
    ):
        case = db.scalars(select(Case).where(Case.case_code == code)).first()
        if case is not None:
            case.product_module = module
            case.service_type = service
    db.commit()
