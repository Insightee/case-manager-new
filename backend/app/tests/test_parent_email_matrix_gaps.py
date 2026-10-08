from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.timezone import today_ist
from app.main import app
from app.models.incident import Incident
from app.seed.demo_seed import run as seed_run
from app.services import ticket_notify_service as ticket_notify
from app.services.email.templates import render_template
from app.services.scheduling_service import confirm_pending_reschedule

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_escalation_email_only_parent_requester():
    parent = SimpleNamespace(
        id=1,
        email="parent@demo.com",
        full_name="Parent",
        role_names=["PARENT"],
        notification_preferences={},
    )
    ticket = SimpleNamespace(id=7, raised_by_user_id=1, subject="Billing help")

    class FakeDb:
        def get(self, model, pk):
            return parent if pk == 1 else None

    with patch(
        "app.services.ticket_notify_service.notification_service.create_notification"
    ) as notif, patch(
        "app.services.ticket_notify_service.send_parent_email"
    ) as send_email:
        ticket_notify.notify_parent_ticket_escalated(FakeDb(), ticket)
    notif.assert_called_once()
    send_email.assert_called_once()
    assert "incident" not in str(send_email.call_args.kwargs.get("payload", {}))


def test_incident_share_email_has_no_description():
    _, text, _ = render_template(
        "incident_family_notice",
        {
            "parent_name": "P",
            "child_name": "C",
            "incident_date": "2026-10-08",
            "portal_url": "http://x",
            "manage_prefs_url": "http://x/prefs",
            "description": "SECRET",
        },
    )
    assert "SECRET" not in text


def test_staff_ticket_reply_includes_excerpt():
    parent = SimpleNamespace(
        id=2,
        email="p@x.com",
        full_name="P",
        role_names=["PARENT"],
        notification_preferences={},
    )
    ticket = SimpleNamespace(id=3, raised_by_user_id=2, subject="Help")
    message = SimpleNamespace(is_internal=False, body="We scheduled a follow-up call tomorrow.")
    staff = SimpleNamespace(id=9, role_names=["ADMIN"])

    class FakeDb:
        def get(self, model, pk):
            return parent if pk == 2 else None

    with patch("app.services.ticket_notify_service.send_parent_email") as send_email, patch(
        "app.services.ticket_notify_service.notification_service.create_notification"
    ):
        ticket_notify.notify_parent_staff_ticket_reply(FakeDb(), ticket, message, staff_user=staff)
    payload = send_email.call_args.kwargs["payload"]
    assert "follow-up call" in payload["reply_excerpt"]


def test_internal_ticket_note_skips_parent_email():
    parent = SimpleNamespace(id=2, role_names=["PARENT"], email="p@x.com")
    ticket = SimpleNamespace(id=3, raised_by_user_id=2, subject="Help")
    message = SimpleNamespace(is_internal=True, body="hidden")
    staff = SimpleNamespace(id=9, role_names=["ADMIN"])

    class FakeDb:
        def get(self, model, pk):
            return parent

    with patch("app.services.ticket_notify_service.send_parent_email") as send_email:
        ticket_notify.notify_parent_staff_ticket_reply(FakeDb(), ticket, message, staff_user=staff)
    send_email.assert_not_called()


def test_reply_dedupe_window_blocks_second_send():
    from app.core.database import SessionLocal
    from app.services.email.parent_mail import send_parent_email

    parent = SimpleNamespace(
        id=1,
        email="dedupe-parent@example.com",
        full_name="P",
        role_names=["PARENT"],
        notification_preferences={},
    )
    db = SessionLocal()
    try:
        with patch("app.services.email.parent_mail.send_email", return_value=True):
            first = send_parent_email(
                db,
                parent,
                category="incidents",
                template_key="support_ticket_reply",
                payload={"parent_name": "P", "ticket_subject": "T", "portal_url": "http://x"},
                entity_type="support_ticket",
                entity_id=99,
                dedupe_window_minutes=10,
            )
            second = send_parent_email(
                db,
                parent,
                category="incidents",
                template_key="support_ticket_reply",
                payload={"parent_name": "P", "ticket_subject": "T", "portal_url": "http://x"},
                entity_type="support_ticket",
                entity_id=99,
                dedupe_window_minutes=10,
            )
        assert first is not None
        assert second is None
    finally:
        db.rollback()
        db.close()


def test_confirm_parent_reschedule_sends_email_when_today():
    from app.services.appointment_notification_service import notify_parents_session_rescheduled

    parent = SimpleNamespace(
        id=1,
        email="p@example.com",
        full_name="Parent",
        role_names=["PARENT"],
        notification_preferences={},
    )
    old = SimpleNamespace(id=1, slot_date=date(2026, 11, 1), start_time=SimpleNamespace(strftime=lambda _: "09:00"))
    new = SimpleNamespace(id=2, slot_date=today_ist(), start_time=SimpleNamespace(strftime=lambda _: "11:00"))
    emails: list[str] = []

    class FakeDb:
        def get(self, model, pk):
            return SimpleNamespace(child=SimpleNamespace(full_name="Child"))

    with patch(
        "app.services.appointment_notification_service._parent_users_for_case",
        return_value=[parent],
    ), patch(
        "app.services.appointment_notification_service.notification_service.create_notification",
    ), patch(
        "app.services.appointment_notification_service.send_parent_email",
        side_effect=lambda *a, **kw: emails.append(kw["template_key"]),
    ), patch(
        "app.services.appointment_notification_service.today_ist",
        return_value=today_ist(),
    ):
        notify_parents_session_rescheduled(FakeDb(), old, new, case_id=3, email_allowed=True)
    assert emails == ["session_rescheduled_today"]


def test_parent_cannot_use_staff_incident_message_endpoint():
    parent_token = _login("parent@demo.com")
    from sqlalchemy import select

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        inc = db.scalars(select(Incident).limit(1)).first()
        assert inc
        incident_id = inc.id
    finally:
        db.close()
    r = client.post(
        f"/api/v1/incidents/{incident_id}/messages",
        headers={"Authorization": f"Bearer {parent_token}"},
        json={"body": "Parent should not post here"},
    )
    assert r.status_code == 403


def test_shared_incident_cross_family_404():
    parent_token = _login("parent@demo.com")
    therapist_token = _login("therapist@demo.com")
    admin_token = _login("superadmin@demo.com")
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus
    from app.models.user import User

    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case_id = db.scalars(
            select(CaseAssignment.case_id).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            ).limit(1)
        ).first()
    finally:
        db.close()

    created = client.post(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {therapist_token}"},
        json={
            "case_id": case_id,
            "primary_category": "CHILD_SAFETY_MEDICAL",
            "subcategory": "injury_fall",
            "what_happened": "Shared incident cross-family test with enough detail.",
            "service_type": "homecare",
            "location": "home",
            "child_safe": "yes",
            "parent_informed": "na",
        },
    )
    assert created.status_code == 201
    incident_id = created.json()["id"]

    before_share = client.get(
        f"/api/v1/parent/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert before_share.status_code == 404

    share = client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"shared_with_family": True},
    )
    assert share.status_code == 200

    ok = client.get(
        f"/api/v1/parent/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert ok.status_code == 200
    assert ok.json().get("description") is None
    assert "what_happened" not in ok.json()
    assert ok.json().get("incident_type_label")
