from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.incident import Incident
from app.seed.demo_seed import run as seed_run
from app.services import incident_parent_notify_service as inc_parent_notify
from app.services import ticket_notify_service as ticket_notify

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def test_unshared_incident_staff_reply_sends_no_email_or_in_app():
    incident = SimpleNamespace(
        id=99,
        shared_with_family=False,
        case_id=1,
        reported_by_user_id=2,
    )
    message = SimpleNamespace(id=1, body="Staff update")
    staff = SimpleNamespace(id=3, role_names=["ADMIN"], full_name="Admin", email="a@demo.com")

    with patch(
        "app.services.incident_parent_notify_service.send_parent_email"
    ) as send_email, patch(
        "app.services.incident_parent_notify_service.notification_service.create_notification"
    ) as create_notif:
        count = inc_parent_notify.notify_parents_incident_staff_reply(
            object(), incident, message, staff_user=staff
        )

    assert count == 0
    send_email.assert_not_called()
    create_notif.assert_not_called()


def test_ticket_without_parent_requester_sends_no_email_on_staff_reply():
    ticket = SimpleNamespace(
        id=10,
        raised_by_user_id=5,
        subject="Therapist question",
    )
    message = SimpleNamespace(is_internal=False, body="We are on it.")
    staff = SimpleNamespace(id=1, role_names=["ADMIN"])

    therapist_raiser = SimpleNamespace(id=5, role_names=["THERAPIST"], email="t@demo.com")

    class FakeDb:
        def get(self, model, pk):
            if pk == 5:
                return therapist_raiser
            return None

    with patch(
        "app.services.ticket_notify_service.send_parent_email"
    ) as send_email, patch(
        "app.services.ticket_notify_service.notification_service.create_notification"
    ) as create_notif:
        ticket_notify.notify_parent_staff_ticket_reply(
            FakeDb(), ticket, message, staff_user=staff
        )

    send_email.assert_not_called()
    create_notif.assert_not_called()


def test_shared_incident_notify_dedupes_to_one_email():
    from app.core.database import SessionLocal
    from app.services.email.parent_mail import send_parent_email

    parent = SimpleNamespace(
        id=1,
        email="parent-gating@example.com",
        full_name="Parent",
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
                template_key="incident_family_notice",
                payload={"parent_name": "P", "child_name": "C", "portal_url": "http://x"},
                entity_type="incident",
                entity_id=42,
            )
            second = send_parent_email(
                db,
                parent,
                category="incidents",
                template_key="incident_family_notice",
                payload={"parent_name": "P", "child_name": "C", "portal_url": "http://x"},
                entity_type="incident",
                entity_id=42,
            )
        assert first is not None
        assert second is None
    finally:
        db.rollback()
        db.close()


def test_parent_ticket_staff_reply_integration_no_email_when_not_requester():
    therapist = client.post(
        "/api/v1/auth/login",
        json={"email": "therapist@demo.com", "password": "demo123"},
    ).json()["access_token"]
    admin = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@demo.com", "password": "demo123"},
    ).json()["access_token"]
    th = {"Authorization": f"Bearer {therapist}"}
    ah = {"Authorization": f"Bearer {admin}"}

    created = client.post(
        "/api/v1/tickets",
        headers=th,
        json={"subject": "Gating test", "body": "Help", "category": "OTHER"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    with patch("app.services.ticket_notify_service.send_parent_email") as send_email:
        r = client.post(
            f"/api/v1/tickets/{ticket_id}/messages",
            headers=ah,
            json={"body": "Staff reply on therapist ticket"},
        )
        assert r.status_code in (200, 201)
    send_email.assert_not_called()


def test_unshared_incident_reply_integration_no_parent_email():
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.user import User

    therapist_token = client.post(
        "/api/v1/auth/login",
        json={"email": "therapist@demo.com", "password": "demo123"},
    ).json()["access_token"]
    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": "superadmin@demo.com", "password": "demo123"},
    ).json()["access_token"]
    th = {"Authorization": f"Bearer {therapist_token}"}
    ah = {"Authorization": f"Bearer {admin_token}"}

    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        from app.models.assignment import CaseAssignment, CaseAssignmentStatus

        case_id = db.scalars(
            select(CaseAssignment.case_id).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            ).limit(1)
        ).first()
        assert case_id
    finally:
        db.close()

    created = client.post(
        "/api/v1/incidents",
        headers=th,
        json={
            "case_id": case_id,
            "primary_category": "CHILD_SAFETY_MEDICAL",
            "subcategory": "injury_fall",
            "what_happened": "Unshared reply gating test incident.",
            "service_type": "homecare",
            "location": "home",
            "child_safe": "yes",
            "parent_informed": "na",
        },
    )
    assert created.status_code == 201
    incident_id = created.json()["id"]

    with patch("app.services.incident_parent_notify_service.send_parent_email") as send_email:
        r = client.post(
            f"/api/v1/incidents/{incident_id}/messages",
            headers=ah,
            json={"body": "Internal staff note to team"},
        )
        assert r.status_code == 201, r.text
    send_email.assert_not_called()

    db = SessionLocal()
    try:
        row = db.get(Incident, incident_id)
        assert row is not None
        assert not row.shared_with_family
    finally:
        db.close()
