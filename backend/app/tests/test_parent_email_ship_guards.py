"""Ship guards for PR #106: leave email per family, accidental-start revert, parent incident view."""

from __future__ import annotations

from datetime import date, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Leave: one email per family, only that family's dates ────────────────────


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


def test_leave_approved_one_email_per_family_no_cross_family_dates():
    from app.services import leave_notification_service as svc

    def _slot(sid, case_id, child, d):
        return SimpleNamespace(
            id=sid,
            case_id=case_id,
            slot_date=d,
            start_time=time(10, 0),
            end_time=time(11, 0),
            case=SimpleNamespace(case_code=f"C{case_id}", child=SimpleNamespace(full_name=child)),
        )

    d1, d2, d3 = date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)
    booked = [
        _slot(1, 101, "Asha", d1),
        _slot(2, 202, "Ravi", d1),
        _slot(3, 101, "Asha", d2),
        _slot(4, 202, "Ravi", d3),
    ]
    calls = iter([_Scalars(booked), _Scalars([])])

    class FakeDb:
        def scalars(self, *_a, **_k):
            return next(calls)

        def get(self, _model, uid):
            return SimpleNamespace(id=uid, full_name=f"Parent {uid}", email=f"p{uid}@x.test", role_names=["PARENT"])

        def flush(self):
            return None

    leave = SimpleNamespace(id=55, therapist_user_id=9, start_date=d1, end_date=d3)
    therapist = SimpleNamespace(id=9, full_name="Thera Pist", email="t@x.test")
    parents_by_case = {101: [1001], 202: [2002, 2003]}
    sent: list[tuple[int, list[str]]] = []

    with patch.object(svc.leave_migration, "is_retroactive_leave", return_value=False), patch.object(
        svc.leave_service, "_leave_scope_ids", return_value=None
    ), patch.object(svc.appt_booking, "cancel_booking_with_session"), patch.object(
        svc, "_parents_for_case", side_effect=lambda _db, cid: parents_by_case[cid]
    ), patch.object(svc, "_parents_for_leave_scope", return_value={}), patch.object(
        svc.notification_service, "create_notification"
    ), patch.object(svc.email_service, "leave_approved_therapist_email", create=True), patch.object(
        svc, "send_parent_email", side_effect=lambda _db, parent, **kw: sent.append((parent.id, kw))
    ):
        try:
            svc.notify_leave_approved(FakeDb(), leave, therapist)
        except StopIteration:
            pass  # downstream therapist/CM queries are out of scope for this test

    by_parent = {pid: kw for pid, kw in sent}
    assert sorted(by_parent) == [1001, 2002, 2003]  # exactly one email per guardian
    assert len(sent) == 3
    asha_lines = by_parent[1001]["payload"]["cancelled_lines"]
    assert len(asha_lines) == 2 and all("Asha" in ln for ln in asha_lines)
    assert any(d1.isoformat() in ln for ln in asha_lines) and any(d2.isoformat() in ln for ln in asha_lines)
    for pid in (2002, 2003):
        lines = by_parent[pid]["payload"]["cancelled_lines"]
        assert len(lines) == 2 and all("Ravi" in ln for ln in lines)
        assert not any("Asha" in ln for ln in lines)
    assert all(kw["template_key"] == "leave_sessions_cancelled" for kw in by_parent.values())


# ── /sessions/{id}/cancel reverts an accidental start: no parent notice ──────


def test_session_cancel_revert_no_parent_notice():
    from app.models.session import Session as TherapySession
    from app.models.session import SessionStatus
    from app.models.user import User

    case_id = _therapist_case_id()
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        # A fresh in-progress visit today on the therapist's active case (no log yet).
        target = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=today_ist(),
            status=SessionStatus.IN_PROGRESS,
        )
        db.add(target)
        db.commit()
        sid = target.id
    finally:
        db.close()

    token = _login("therapist@demo.com")
    with patch("app.services.email.parent_mail.send_parent_email") as gw, patch(
        "app.services.appointment_notification_service.send_parent_email"
    ) as appt_gw, patch("app.services.notification_service.create_notification") as notif:
        r = client.post(f"/api/v1/sessions/{sid}/cancel", headers=_h(token))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SCHEDULED"
    gw.assert_not_called()
    appt_gw.assert_not_called()
    assert not [c for c in notif.call_args_list if c.kwargs.get("entity_type") == "session"]


# ── Parent incident view ─────────────────────────────────────────────────────


def _therapist_case_id() -> int:
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.user import User

    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        return db.scalars(
            select(CaseAssignment.case_id).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            ).limit(1)
        ).first()
    finally:
        db.close()


def _staff_incident(therapist_token: str, case_id: int) -> int:
    r = client.post(
        "/api/v1/incidents",
        headers=_h(therapist_token),
        json={
            "case_id": case_id,
            "primary_category": "CHILD_SAFETY_MEDICAL",
            "subcategory": "injury_fall",
            "title": "SECRET-TITLE other child Kiran involved",
            "what_happened": "CLINICAL-DESCRIPTION do not show to family, enough detail here.",
            "service_type": "homecare",
            "location": "home",
            "child_safe": "yes",
            "parent_informed": "na",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_parent_incident_view_scoping_internal_notes_and_pre_share_messages():
    from app.seed.demo_seed import get_or_create_user

    parent_token = _login("parent@demo.com")
    therapist_token = _login("therapist@demo.com")
    admin_token = _login("superadmin@demo.com")
    db = SessionLocal()
    try:
        get_or_create_user(db, "other.family@demo.com", "demo123", "Other Family", "PARENT")
        db.commit()
    finally:
        db.close()
    other_token = _login("other.family@demo.com")

    case_id = _therapist_case_id()
    incident_id = _staff_incident(therapist_token, case_id)

    pre = client.post(
        f"/api/v1/incidents/{incident_id}/messages",
        headers=_h(admin_token),
        json={"body": "PRE-SHARE staff discussion"},
    )
    assert pre.status_code in (200, 201), pre.text

    # Unshared: 404 for own family and absent from list.
    assert client.get(f"/api/v1/parent/incidents/{incident_id}", headers=_h(parent_token)).status_code == 404
    assert incident_id not in {i["id"] for i in client.get("/api/v1/parent/incidents", headers=_h(parent_token)).json()}

    import time as _t

    _t.sleep(1.1)  # SQLite CURRENT_TIMESTAMP has 1s precision
    with patch("app.services.email.parent_mail.send_parent_email"):
        share = client.patch(
            f"/api/v1/incidents/{incident_id}", headers=_h(admin_token), json={"shared_with_family": True}
        )
        assert share.status_code == 200, share.text
        _t.sleep(1.1)
        internal = client.post(
            f"/api/v1/incidents/{incident_id}/messages",
            headers=_h(admin_token),
            json={"body": "INTERNAL-NOTE staff only", "is_internal": True},
        )
        assert internal.status_code in (200, 201), internal.text
        visible = client.post(
            f"/api/v1/incidents/{incident_id}/messages",
            headers=_h(admin_token),
            json={"body": "POST-SHARE family update"},
        )
        assert visible.status_code in (200, 201), visible.text

    # Staff still see everything, including the internal note.
    staff_view = client.get(f"/api/v1/incidents/{incident_id}", headers=_h(admin_token)).json()
    staff_bodies = [m["body"] for m in staff_view["messages"]]
    assert "INTERNAL-NOTE staff only" in staff_bodies and "PRE-SHARE staff discussion" in staff_bodies
    pre_msg = next(m for m in staff_view["messages"] if m["body"] == "PRE-SHARE staff discussion")
    assert pre_msg["is_internal"] is False

    # Own family: sees post-share update only; no internal note, no pre-share discussion, no clinical text.
    r = client.get(f"/api/v1/parent/incidents/{incident_id}", headers=_h(parent_token))
    assert r.status_code == 200, r.text
    raw = r.text
    bodies = [m["body"] for m in r.json()["messages"]]
    assert bodies == ["POST-SHARE family update"]
    for forbidden in ("INTERNAL-NOTE", "PRE-SHARE", "CLINICAL-DESCRIPTION", "SECRET-TITLE", "Kiran"):
        assert forbidden not in raw
    for key in ("description", "immediate_action", "tagged_users", "action_taken_note", "location"):
        assert key not in r.json()
    rows = client.get("/api/v1/parent/incidents", headers=_h(parent_token)).json()
    row = next(i for i in rows if i["id"] == incident_id)
    assert "SECRET-TITLE" not in str(row) and "is_sensitive" not in row

    # Another family: 404 and not listed.
    assert client.get(f"/api/v1/parent/incidents/{incident_id}", headers=_h(other_token)).status_code == 404
    assert incident_id not in {i["id"] for i in client.get("/api/v1/parent/incidents", headers=_h(other_token)).json()}


def test_detail_dict_hides_internal_notes_from_parent_viewers():
    from app.services.incident_service import viewer_sees_internal_incident_messages

    assert viewer_sees_internal_incident_messages(None) is False
    assert viewer_sees_internal_incident_messages(SimpleNamespace(role_names=["PARENT"])) is False
    assert viewer_sees_internal_incident_messages(SimpleNamespace(role_names=["CASE_MANAGER"])) is True
    assert viewer_sees_internal_incident_messages(SimpleNamespace(role_names=["THERAPIST"])) is True
