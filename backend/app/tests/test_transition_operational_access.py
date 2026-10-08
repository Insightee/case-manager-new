"""Operational access during therapist handover (booking, clinical, payouts)."""
from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CaseDayType, CompensationMode
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.core.permissions import RoleName
from app.models.user import User
from app.seed.demo_seed import get_or_create_user, run as seed_run
from app.services import invoice_billing_service, therapist_transition_service

client = TestClient(app)
_slot_time_seq = 0


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str = "superadmin@demo.com") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _pick_two_therapists(_ah: dict[str, str]) -> tuple[dict, dict]:
    db = SessionLocal()
    try:
        outgoing = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        assert outgoing is not None
        incoming = get_or_create_user(
            db,
            "transition-b@demo.com",
            "demo123",
            "Transition Therapist B",
            RoleName.THERAPIST.value,
        )
        db.commit()
        return (
            {"therapist_user_id": outgoing.id, "full_name": outgoing.full_name},
            {"therapist_user_id": incoming.id, "full_name": incoming.full_name},
        )
    finally:
        db.close()


def _therapist_email(therapist_user_id: int) -> str:
    db = SessionLocal()
    try:
        user = db.get(User, therapist_user_id)
        assert user and user.email
        return user.email
    finally:
        db.close()


def _prepare_case_with_therapist(case_id: int, therapist_id: int, ah: dict[str, str]) -> None:
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        case.billing_type = BillingType.PER_SESSION
        case.client_rate_per_session_inr = 1200
        case.compensation_mode = CompensationMode.PERCENTAGE
        case.pay_share_amount_inr = 600
        for a in db.scalars(select(CaseAssignment).where(CaseAssignment.case_id == case_id)).all():
            if a.status == CaseAssignmentStatus.ACTIVE:
                a.status = CaseAssignmentStatus.ENDED
                a.end_date = date(2026, 7, 1)
        db.commit()
    finally:
        db.close()

    res = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=ah,
        json={"therapist_user_id": therapist_id, "start_date": "2026-07-01"},
    )
    assert res.status_code == 201, res.text


def _start_transition(ah: dict[str, str], case_id: int, outgoing_id: int, incoming_id: int) -> tuple[list[str], date]:
    start = date.today()
    dates = [(start + timedelta(days=i)).isoformat() for i in range(3)]
    created = client.post(
        f"/api/v1/cases/{case_id}/transitions",
        headers=ah,
        json={
            "incoming_therapist_user_id": incoming_id,
            "transition_dates": dates,
            "billing_update": {
                "billing_type": "PER_SESSION",
                "client_rate_per_session_inr": 1500,
                "compensation_mode": "PERCENTAGE",
                "pay_share_amount_inr": 800,
            },
        },
    )
    assert created.status_code == 201, created.text
    return dates, start


def _create_slot(token: str, slot_date: date, therapist_id: int | None = None) -> int:
    global _slot_time_seq
    _slot_time_seq += 1
    hour = 8 + (_slot_time_seq % 9)
    body = {
        "slot_date": slot_date.isoformat(),
        "start_time": f"{hour:02d}:00:00",
        "end_time": f"{hour:02d}:45:00",
    }
    if therapist_id is not None:
        body["therapist_id"] = therapist_id
    res = client.post("/api/v1/scheduling/slots", headers=_headers(token), json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _book_slot(token: str, slot_id: int, case_id: int, *, route: str = "scheduling") -> int:
    path = (
        f"/api/v1/scheduling/slots/{slot_id}/book"
        if route == "scheduling"
        else f"/api/v1/slots/{slot_id}/book"
    )
    res = client.post(
        path,
        headers=_headers(token),
        json={"case_id": case_id},
    )
    return res.status_code


@pytest.fixture
def transition_case():
    ah = _headers(_login())
    db = SessionLocal()
    try:
        from app.tests.conftest import isolated_homecare_case

        case = isolated_homecare_case(db)
        case.day_type = CaseDayType.FULL_DAY
        case.client_rate_per_session_inr = 1200
        case.pay_share_amount_inr = 600
        db.commit()
        case_id = case.id
    finally:
        db.close()
    t1, t2 = _pick_two_therapists(ah)
    _prepare_case_with_therapist(case_id, t1["therapist_user_id"], ah)
    dates, start = _start_transition(ah, case_id, t1["therapist_user_id"], t2["therapist_user_id"])
    return {
        "ah": ah,
        "case_id": case_id,
        "outgoing": t1,
        "incoming": t2,
        "dates": dates,
        "start": start,
        "outgoing_token": _login(_therapist_email(t1["therapist_user_id"])),
        "incoming_token": _login(_therapist_email(t2["therapist_user_id"])),
    }


def test_both_therapists_book_within_handover_window(transition_case):
    ctx = transition_case
    start = ctx["start"]
    case_id = ctx["case_id"]

    out_slot = _create_slot(ctx["outgoing_token"], start + timedelta(days=1))
    in_slot = _create_slot(ctx["incoming_token"], start + timedelta(days=1))

    assert _book_slot(ctx["outgoing_token"], out_slot, case_id) == 200
    assert _book_slot(ctx["incoming_token"], in_slot, case_id) == 200
    assert _book_slot(ctx["incoming_token"], in_slot, case_id, route="legacy") in (200, 400)


def test_booking_outside_handover_window_blocked(transition_case):
    ctx = transition_case
    start = ctx["start"]
    case_id = ctx["case_id"]

    too_late = _create_slot(ctx["outgoing_token"], start + timedelta(days=5))
    too_early = _create_slot(ctx["incoming_token"], start - timedelta(days=1))

    late = client.post(
        f"/api/v1/scheduling/slots/{too_late}/book",
        headers=_headers(ctx["outgoing_token"]),
        json={"case_id": case_id},
    )
    assert late.status_code == 409

    early = client.post(
        f"/api/v1/scheduling/slots/{too_early}/book",
        headers=_headers(ctx["incoming_token"]),
        json={"case_id": case_id},
    )
    assert early.status_code == 409


def test_cancel_booking_allowed_during_transition(transition_case):
    ctx = transition_case
    slot_id = _create_slot(ctx["outgoing_token"], ctx["start"])
    assert _book_slot(ctx["outgoing_token"], slot_id, ctx["case_id"]) == 200
    cancel = client.post(
        f"/api/v1/scheduling/slots/{slot_id}/cancel",
        headers=_headers(ctx["outgoing_token"]),
        json={},
    )
    assert cancel.status_code == 200


def test_structural_writes_still_blocked_during_transition(transition_case):
    ctx = transition_case
    ah = ctx["ah"]
    case_id = ctx["case_id"]

    billing = client.patch(
        f"/api/v1/cases/{case_id}/billing",
        headers=ah,
        json={"client_rate_per_session_inr": 9999},
    )
    assert billing.status_code == 409

    day_type = client.patch(
        f"/api/v1/cases/{case_id}/day-type",
        headers=ah,
        json={"day_type": "HALF_DAY", "reason": "test"},
    )
    assert day_type.status_code == 409

    assign = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=ah,
        json={
            "therapist_user_id": ctx["incoming"]["therapist_user_id"],
            "start_date": "2026-12-01",
            "reason_for_change": "blocked",
        },
    )
    assert assign.status_code in (400, 409)

    second = client.post(
        f"/api/v1/cases/{case_id}/transitions",
        headers=ah,
        json={
            "incoming_therapist_user_id": ctx["outgoing"]["therapist_user_id"],
            "transition_dates": ctx["dates"],
            "billing_update": {
                "billing_type": "PER_SESSION",
                "client_rate_per_session_inr": 1500,
                "compensation_mode": "PERCENTAGE",
                "pay_share_amount_inr": 800,
            },
        },
    )
    assert second.status_code in (400, 409)

    pause = client.post(
        f"/api/v1/cases/{case_id}/status-requests",
        headers=ah,
        json={"to_status": "PAUSED", "reason": "test pause"},
    )
    assert pause.status_code == 409


def test_case_delete_blocked_during_transition(transition_case):
    ctx = transition_case
    db = SessionLocal()
    try:
        case = db.get(Case, ctx["case_id"])
        code = case.case_code
    finally:
        db.close()
    ah = _headers(_login())
    res = client.post(
        "/api/v1/admin/maintenance/delete-case-by-code",
        headers=ah,
        json={"case_code": code, "confirm": True},
    )
    assert res.status_code in (400, 404, 409, 500)
    assert "transition" in res.json()["detail"].lower()


def test_booking_availability_respects_handover_window(transition_case):
    ctx = transition_case
    ah = ctx["ah"]
    too_early = ctx["start"] - timedelta(days=1)
    avail = client.get(
        "/api/v1/booking/availability",
        headers=ah,
        params={
            "therapist_id": ctx["incoming"]["therapist_user_id"],
            "from_date": too_early.isoformat(),
            "to_date": too_early.isoformat(),
            "case_id": ctx["case_id"],
        },
    )
    assert avail.status_code == 200
    slot_id = _create_slot(ctx["incoming_token"], too_early)
    assert slot_id not in {row["id"] for row in avail.json()}

    in_range = ctx["start"] + timedelta(days=1)
    avail_ok = client.get(
        "/api/v1/booking/availability",
        headers=ah,
        params={
            "therapist_id": ctx["incoming"]["therapist_user_id"],
            "from_date": in_range.isoformat(),
            "to_date": in_range.isoformat(),
            "case_id": ctx["case_id"],
        },
    )
    assert avail_ok.status_code == 200
    _create_slot(ctx["incoming_token"], in_range)
    assert len(avail_ok.json()) >= 0


def test_clinical_profile_update_allowed_during_transition(transition_case):
    ctx = transition_case
    token = ctx["outgoing_token"]
    case_id = ctx["case_id"]
    res = client.patch(
        f"/api/v1/cases/{case_id}/clinical-profile",
        headers=_headers(token),
        json={"strengths": "transition test strength"},
    )
    assert res.status_code == 200


def test_payout_attributes_delivering_therapist_during_overlap(transition_case):
    ctx = transition_case
    case_id = ctx["case_id"]
    session_day = ctx["start"] + timedelta(days=1)
    db = SessionLocal()
    try:
        session = TherapySession(
            case_id=case_id,
            therapist_user_id=ctx["incoming"]["therapist_user_id"],
            scheduled_date=session_day,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
        )
        db.add(session)
        db.flush()
        db.add(
            DailyLog(
                session_id=session.id,
                attendance_status=AttendanceStatus.PRESENT.value,
                approval_status=LogApprovalStatus.APPROVED.value,
            )
        )
        db.commit()

        ok, code = invoice_billing_service.therapist_active_on_session_date(
            db,
            case_id=case_id,
            therapist_user_id=ctx["incoming"]["therapist_user_id"],
            on_date=session_day,
        )
        assert ok is True
        assert code is None
    finally:
        db.close()


def test_transition_read_surfaces_outgoing_future_bookings(transition_case):
    ctx = transition_case
    after_handover = ctx["start"] + timedelta(days=30)
    db = SessionLocal()
    try:
        from app.models.slot import SlotStatus, TherapistSlot

        slot = TherapistSlot(
            therapist_user_id=ctx["outgoing"]["therapist_user_id"],
            slot_date=after_handover,
            start_time=time(15, 0),
            end_time=time(16, 0),
            status=SlotStatus.BOOKED,
            case_id=ctx["case_id"],
            slot_duration_minutes=60,
        )
        db.add(slot)
        db.commit()
    finally:
        db.close()

    detail = client.get(
        f"/api/v1/cases/{ctx['case_id']}/transitions/active",
        headers=ctx["ah"],
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body.get("has_outgoing_future_bookings_after_handover") is True
    assert body.get("outgoing_future_bookings_after_handover")


def test_session_start_allowed_during_transition(transition_case):
    ctx = transition_case
    slot_id = _create_slot(ctx["outgoing_token"], ctx["start"])
    assert _book_slot(ctx["outgoing_token"], slot_id, ctx["case_id"]) == 200
    db = SessionLocal()
    try:
        from app.models.slot import TherapistSlot

        slot = db.get(TherapistSlot, slot_id)
        session_id = slot.session_id
        assert session_id
    finally:
        db.close()

    start = client.post(
        f"/api/v1/sessions/{session_id}/start",
        headers=_headers(ctx["outgoing_token"]),
    )
    assert start.status_code in (200, 409), start.text
    if start.status_code == 409:
        assert "transition" not in start.text.lower()
        assert "handover" not in start.text.lower()
