"""Tests for case close side effects and portal visibility."""

from __future__ import annotations

import uuid
from datetime import date, time, timedelta

from sqlalchemy import select

from fastapi.testclient import TestClient

from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.recurring_schedule import RecurringScheduleAssignment, RecurringScheduleStatus
from app.models.slot import SlotStatus, TherapistSlot

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_active_case(admin_headers: dict, therapist_id: int) -> int:
    suffix = uuid.uuid4().hex[:8]
    parent_email = f"close-fx-{suffix}@demo.com"
    fam = client.post(
        "/api/v1/admin/families",
        headers=admin_headers,
        json={
            "parent_email": parent_email,
            "parent_full_name": "Close FX Parent",
            "child": {"first_name": "Close", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]
    allot = client.post(
        "/api/v1/admin/cases/allot",
        headers=admin_headers,
        json={
            "child_id": child_id,
            "service_type": "Shadow support",
            "product_module": "shadow_support",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_amount_inr": 720,
            "therapist_user_id": therapist_id,
        },
    )
    assert allot.status_code == 201, allot.text
    case_id = allot.json()["case"]["id"]
    activate = client.post(
        f"/api/v1/admin/cases/{case_id}/activate-allotment",
        headers=admin_headers,
    )
    assert activate.status_code == 200, activate.text
    return case_id


def test_admin_close_cancels_future_booking_and_hides_from_therapist():
    admin_headers = _login("superadmin@demo.com")
    therapists = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=admin_headers)
    therapist_row = therapists.json()[0]
    therapist_id = therapist_row["id"]
    therapist_headers = _login(therapist_row["email"])

    case_id = _create_active_case(admin_headers, therapist_id)
    tomorrow = date.today() + timedelta(days=1)

    from app.core.database import SessionLocal

    with SessionLocal() as db:
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        assert assignment is not None
        therapist_id = assignment.therapist_user_id
        existing = db.scalars(
            select(TherapistSlot).where(
                TherapistSlot.therapist_user_id == therapist_id,
                TherapistSlot.slot_date == tomorrow,
                TherapistSlot.start_time == time(14, 0),
            )
        ).first()
        if existing:
            existing.status = SlotStatus.BOOKED
            existing.case_id = case_id
            existing.booked_by_user_id = therapist_id
            slot_id = existing.id
        else:
            slot = TherapistSlot(
                therapist_user_id=therapist_id,
                slot_date=tomorrow,
                start_time=time(14, 0),
                end_time=time(15, 0),
                status=SlotStatus.BOOKED,
                case_id=case_id,
                booked_by_user_id=therapist_id,
            )
            db.add(slot)
            db.flush()
            slot_id = slot.id
        db.commit()

    visible_before = client.get("/api/v1/therapist/home", headers=therapist_headers)
    assert visible_before.status_code == 200
    board_ids_before = [row["id"] for row in visible_before.json()["cases_board"]["allCases"]]
    assert case_id in board_ids_before

    close = client.post(
        f"/api/v1/cases/{case_id}/client-status",
        headers=admin_headers,
        json={
            "new_status": "CLOSED",
            "effective_date": date.today().isoformat(),
            "reason": "Family completed programme goals",
        },
    )
    assert close.status_code == 200, close.text

    with SessionLocal() as db:
        refreshed = db.get(TherapistSlot, slot_id)
        assert refreshed is not None
        assert refreshed.status == SlotStatus.CANCELLED
        assert refreshed.case_id is None
        active_assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        assert active_assignment is None

    visible_after = client.get("/api/v1/therapist/home", headers=therapist_headers)
    assert visible_after.status_code == 200
    board_ids_after = [row["id"] for row in visible_after.json()["cases_board"]["allCases"]]
    assert case_id not in board_ids_after

    detail = client.get(f"/api/v1/cases/{case_id}", headers=therapist_headers)
    assert detail.status_code == 403

    admin_detail = client.get(f"/api/v1/cases/{case_id}", headers=admin_headers)
    assert admin_detail.status_code == 200
    assert admin_detail.json()["status"] == "CLOSED"
    assert admin_detail.json().get("status_reason") or admin_detail.json().get("statusReason")


def test_bare_patch_close_is_rejected():
    admin_headers = _login("superadmin@demo.com")
    therapists = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=admin_headers)
    therapist_id = therapists.json()[0]["id"]
    case_id = _create_active_case(admin_headers, therapist_id)

    close = client.patch(
        f"/api/v1/cases/{case_id}",
        headers=admin_headers,
        json={"status": "CLOSED"},
    )
    assert close.status_code == 400
    assert "client-status" in close.json()["detail"].lower() or "reason" in close.json()["detail"].lower()


def test_admin_close_and_reopen_writes_audit_and_pending_allotment():
    admin_headers = _login("superadmin@demo.com")
    therapists = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=admin_headers)
    therapist_id = therapists.json()[0]["id"]
    case_id = _create_active_case(admin_headers, therapist_id)
    past = (date.today() - timedelta(days=3)).isoformat()

    close = client.post(
        f"/api/v1/cases/{case_id}/client-status",
        headers=admin_headers,
        json={
            "new_status": "CLOSED",
            "effective_date": past,
            "reason": "Family relocated out of service area",
        },
    )
    assert close.status_code == 200, close.text
    assert close.json()["case"]["status"] == "CLOSED"

    reopen_date = (date.today() - timedelta(days=1)).isoformat()
    reopen = client.post(
        f"/api/v1/cases/{case_id}/client-status",
        headers=admin_headers,
        json={
            "new_status": "PENDING_ALLOTMENT",
            "effective_date": reopen_date,
            "reason": "Family returned and requested restart",
        },
    )
    assert reopen.status_code == 200, reopen.text
    assert reopen.json()["case"]["status"] == "PENDING_ALLOTMENT"

    assign = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=admin_headers,
        json={
            "therapist_user_id": therapist_id,
            "start_date": date.today().isoformat(),
            "reason_for_change": "Reassigned after reopen",
        },
    )
    assert assign.status_code == 201, assign.text

    case_after = client.get(f"/api/v1/cases/{case_id}", headers=admin_headers)
    assert case_after.status_code == 200
    assert case_after.json()["status"] == "ACTIVE"

    audit = client.get(f"/api/v1/cases/{case_id}/client-status/audit", headers=admin_headers)
    assert audit.status_code == 200
    rows = audit.json()["audit"]
    assert len(rows) >= 3
    assert any(r["newStatus"] == "CLOSED" for r in rows)
    assert any(r["newStatus"] == "PENDING_ALLOTMENT" for r in rows)
    assert any(
        r["previousStatus"] == "PENDING_ALLOTMENT" and r["newStatus"] == "ACTIVE" for r in rows
    )

    timeline = client.get(f"/api/v1/admin/cases/{case_id}/timeline", headers=admin_headers)
    assert timeline.status_code == 200
    labels = [i.get("action_label", "") for i in timeline.json()["items"]]
    assert any("closed" in (label or "").lower() for label in labels)
    assert any("reopened" in (label or "").lower() for label in labels)
    assert any("allotted" in (label or "").lower() for label in labels)


def test_admin_close_cancels_recurring_schedule_record():
    admin_headers = _login("superadmin@demo.com")
    therapists = client.get("/api/v1/admin/users/directory?roles=THERAPIST", headers=admin_headers)
    therapist_id = therapists.json()[0]["id"]
    case_id = _create_active_case(admin_headers, therapist_id)

    start = date.today() + timedelta(days=1)
    end = start + timedelta(days=7)
    recurring = client.post(
        "/api/v1/scheduling/assign-recurring",
        headers=admin_headers,
        json={
            "case_id": case_id,
            "therapist_user_id": therapist_id,
            "weekdays": ["mon"],
            "start_time": "10:00",
            "end_time": "11:00",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert recurring.status_code in (200, 201), recurring.text
    record_id = recurring.json()["id"]

    close = client.post(
        f"/api/v1/cases/{case_id}/client-status",
        headers=admin_headers,
        json={
            "new_status": "CLOSED",
            "effective_date": date.today().isoformat(),
            "reason": "Closing to cancel recurring schedule",
        },
    )
    assert close.status_code == 200, close.text

    from app.core.database import SessionLocal

    with SessionLocal() as db:
        record = db.get(RecurringScheduleAssignment, record_id)
        assert record is not None
        assert record.status == RecurringScheduleStatus.CANCELLED
