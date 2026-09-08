"""G3: case pause / replacement blocks session start (Core OS Stabilisation PR1 / DEC-02)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.main import app
from app.models.case import Case, CaseStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services.case_portal_visibility import is_case_hidden_from_client_portals
from app.services.session_operational_gate_service import (
    OVERRIDE_DATA_QUALITY_FLAG,
    case_blocks_normal_session_start,
)
from app.tests.session_helpers import (
    clear_blocking_pending_logs_for_therapist,
    clear_pending_absences_for_therapist,
    end_active_sessions_for_therapist,
    ensure_scheduled_sessions_for_therapist,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_sessions():
    end_active_sessions_for_therapist()
    clear_blocking_pending_logs_for_therapist()
    clear_pending_absences_for_therapist()
    yield
    end_active_sessions_for_therapist()


def _therapist_headers() -> dict:
    r = client.post("/api/v1/auth/login", json={"email": "therapist@demo.com", "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _admin_headers() -> dict:
    r = client.post("/api/v1/auth/login", json={"email": "superadmin@demo.com", "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _scheduled_today_for_therapist_case() -> tuple[int, int, int]:
    """Return (session_id, case_id, therapist_id) on an assigned ACTIVE case for today."""
    ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    assert ids, "demo therapist needs an ACTIVE assignment with a SCHEDULED session"
    db = SessionLocal()
    try:
        today = today_ist()
        for sid in ids:
            sess = db.get(TherapySession, sid)
            if sess is None:
                continue
            if sess.scheduled_date != today:
                sess.scheduled_date = today
            case = db.get(Case, sess.case_id)
            assert case is not None
            case.status = CaseStatus.ACTIVE
            case.status_effective_date = None
            case.status_reason = None
            db.commit()
            db.refresh(sess)
            return sess.id, sess.case_id, sess.therapist_user_id
        raise AssertionError("no scheduled session available for G3")
    finally:
        db.close()


def test_case_blocks_helper_suspended_and_replacement():
    class _C:
        pass

    c = _C()
    c.status = CaseStatus.SUSPENDED
    c.status_effective_date = today_ist()
    assert case_blocks_normal_session_start(c) == "CASE_SUSPENDED"

    c.status = CaseStatus.PENDING_REPLACEMENT
    assert case_blocks_normal_session_start(c) == "CASE_PENDING_REPLACEMENT"

    c.status = CaseStatus.ACTIVE
    assert case_blocks_normal_session_start(c) is None

    c.status = CaseStatus.SUSPENDED
    c.status_effective_date = today_ist() + timedelta(days=3)
    assert case_blocks_normal_session_start(c) is None


def test_suspended_hides_from_parent_portal_helper():
    class _C:
        pass

    c = _C()
    c.status = CaseStatus.SUSPENDED
    assert is_case_hidden_from_client_portals(c) is True
    c.status = CaseStatus.PENDING_REPLACEMENT
    assert is_case_hidden_from_client_portals(c) is False
    c.status = CaseStatus.ACTIVE
    assert is_case_hidden_from_client_portals(c) is False


def test_start_blocked_when_case_suspended():
    sid, case_id, _ = _scheduled_today_for_therapist_case()
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        case.status = CaseStatus.SUSPENDED
        case.status_effective_date = today_ist()
        case.status_reason = "G3 pause test"
        db.commit()
    finally:
        db.close()

    headers = _therapist_headers()
    r = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "CASE_SUSPENDED"
    else:
        assert "paused" in str(detail).lower() or "suspended" in str(detail).lower()

    db = SessionLocal()
    try:
        sess = db.get(TherapySession, sid)
        assert sess is not None
        assert sess.status == SessionStatus.SCHEDULED
        assert sess.actual_start_at is None
    finally:
        db.close()


def test_start_blocked_when_pending_replacement():
    sid, case_id, _ = _scheduled_today_for_therapist_case()
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        case.status = CaseStatus.PENDING_REPLACEMENT
        case.status_effective_date = today_ist()
        case.status_reason = "G3 replacement test"
        db.commit()
    finally:
        db.close()

    headers = _therapist_headers()
    r = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "CASE_PENDING_REPLACEMENT"

    db = SessionLocal()
    try:
        sess = db.get(TherapySession, sid)
        assert sess.status == SessionStatus.SCHEDULED
    finally:
        db.close()


def test_future_effective_suspend_still_allows_start():
    sid, case_id, _ = _scheduled_today_for_therapist_case()
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        case.status = CaseStatus.SUSPENDED
        case.status_effective_date = today_ist() + timedelta(days=5)
        case.status_reason = "Future pause"
        db.commit()
    finally:
        db.close()

    headers = _therapist_headers()
    r = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    # May still fail for pending-log / other gates; if 200 or already in progress OK;
    # must NOT be CASE_SUSPENDED.
    if r.status_code == 400:
        detail = r.json()["detail"]
        if isinstance(detail, dict):
            assert detail.get("code") != "CASE_SUSPENDED"
        else:
            assert "paused" not in str(detail).lower()
    else:
        assert r.status_code in (200, 409)


def test_admin_override_start_on_suspended_marks_finance_review():
    sid, case_id, _ = _scheduled_today_for_therapist_case()
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        case.status = CaseStatus.SUSPENDED
        case.status_effective_date = today_ist()
        case.status_reason = "G3 override"
        db.commit()
    finally:
        db.close()

    # Therapist cannot override
    th = _therapist_headers()
    r = client.post(
        f"/api/v1/sessions/{sid}/start",
        headers=th,
        json={"admin_override": True, "override_reason": "Emergency visit for family"},
    )
    assert r.status_code == 403, r.text

    # Superadmin can — but session belongs to therapist; start requires session.update + ownership.
    # Use therapist start after temporarily granting path: admin override is checked on the
    # acting user. Seed superadmin may not own the session. Restore ACTIVE for ownership path
    # is wrong — instead call service with admin_override via therapist who is also given
    # the permission is hard. Practical approach: use session_service directly as therapist
    # with admin_override flag (gate does not check role; API does).
    from app.services import session_service

    db = SessionLocal()
    try:
        clear_blocking_pending_logs_for_therapist()
        sess = db.get(TherapySession, sid)
        therapist = db.get(User, sess.therapist_user_id)
        started = session_service.start_session(
            db,
            sess,
            therapist.id,
            admin_override=True,
            override_reason="Emergency visit authorised by ops",
        )
        db.commit()
        assert started.status == SessionStatus.IN_PROGRESS
        assert started.data_quality_flag == OVERRIDE_DATA_QUALITY_FLAG
    finally:
        db.close()


def test_in_progress_may_finish_after_suspend():
    sid, case_id, _ = _scheduled_today_for_therapist_case()
    from app.services import session_service
    from app.tests.session_helpers import backdate_in_progress_session

    db = SessionLocal()
    try:
        clear_blocking_pending_logs_for_therapist()
        sess = db.get(TherapySession, sid)
        therapist = db.get(User, sess.therapist_user_id)
        case = db.get(Case, case_id)
        case.status = CaseStatus.ACTIVE
        db.commit()
        db.refresh(sess)
        session_service.start_session(db, sess, therapist.id)
        db.commit()
        case = db.get(Case, case_id)
        case.status = CaseStatus.SUSPENDED
        case.status_effective_date = today_ist()
        db.commit()
    finally:
        db.close()

    backdate_in_progress_session(sid, minutes_ago=10)
    headers = _therapist_headers()
    r = client.post(f"/api/v1/sessions/{sid}/end", headers=headers, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == SessionStatus.COMPLETED.value
