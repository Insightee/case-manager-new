"""Case×day uniqueness, scheduled-session leave days, and credit copy rules."""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.seed.demo_seed import run as seed_run
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus
from app.models.user import User
from app.services import invoice_attendance_service as attendance
from app.services import leave_dates_service as leave_dates
from app.services import leave_policy_service as policy
from app.services import leave_service
from app.services import session_absence_service as absence
from app.tests.test_leave_policy import _ensure_therapist_profile


FRI = date(2026, 3, 6)  # Friday
SAT = date(2026, 3, 7)
SUN = date(2026, 3, 8)
MON = date(2026, 3, 9)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _clear_case_day(db, therapist_id: int, case_id: int, day: date) -> None:
    sessions = db.scalars(
        select(TherapySession).where(
            TherapySession.case_id == case_id,
            TherapySession.scheduled_date == day,
        )
    ).all()
    ids = [s.id for s in sessions]
    if ids:
        db.query(SessionAbsenceRequest).filter(SessionAbsenceRequest.session_id.in_(ids)).delete(
            synchronize_session=False
        )
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_id,
            TherapistLeave.start_date <= day,
            TherapistLeave.end_date >= day,
            TherapistLeave.status.in_((LeaveStatus.PENDING, LeaveStatus.APPROVED)),
        )
    ).all()
    for leave in leaves:
        scoped = leave.case_ids or ([leave.case_id] if leave.case_id else [])
        if not scoped or case_id in scoped:
            db.delete(leave)
    db.flush()


def _therapist_cases(db):
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    assert therapist
    _ensure_therapist_profile(db, therapist.id, employment_start=date(2025, 1, 1))
    assignments = db.scalars(
        select(CaseAssignment)
        .join(Case, Case.id == CaseAssignment.case_id)
        .where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()
    shadow = homecare = None
    for row in assignments:
        case = db.get(Case, row.case_id)
        if not case:
            continue
        mod = (case.product_module or "").strip().lower()
        if shadow is None and mod == "shadow_support":
            shadow = case
        if homecare is None and mod != "shadow_support":
            homecare = case
    return therapist, shadow, homecare


def _add_session(db, *, case_id: int, therapist_id: int, day: date, status=SessionStatus.SCHEDULED):
    session = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist_id,
        scheduled_date=day,
        start_time=time(9, 0),
        end_time=time(10, 0),
        mode=SessionMode.SCHOOL,
        status=status,
    )
    db.add(session)
    db.flush()
    return session


def test_duplicate_leave_same_case_day_blocked():
    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        day = date(2026, 4, 14)
        leave_service.create_therapist_leave_request(
            db,
            therapist=therapist,
            start_date=day,
            end_date=day,
            case_ids=[shadow.id],
            auto_approve=True,
            reviewer_user_id=therapist.id,
        )
        db.commit()
        with pytest.raises(ValueError, match="Leave already exists"):
            leave_service.create_therapist_leave_request(
                db,
                therapist=therapist,
                start_date=day,
                end_date=day,
                case_ids=[shadow.id],
                auto_approve=True,
                reviewer_user_id=therapist.id,
            )
    finally:
        db.close()


def test_disjoint_cases_same_day_still_allowed():
    db = SessionLocal()
    try:
        therapist, shadow, homecare = _therapist_cases(db)
        if not shadow or not homecare:
            pytest.skip("Need shadow and homecare cases")
        day = date(2026, 4, 15)
        leave_service.create_therapist_leave_request(
            db,
            therapist=therapist,
            start_date=day,
            end_date=day,
            case_ids=[shadow.id],
            auto_approve=True,
            reviewer_user_id=therapist.id,
        )
        second = leave_service.create_therapist_leave_request(
            db,
            therapist=therapist,
            start_date=day,
            end_date=day,
            case_ids=[homecare.id],
            auto_approve=True,
            reviewer_user_id=therapist.id,
        )
        db.commit()
        assert second.id
        assert second.case_ids == [homecare.id]
    finally:
        db.close()


def test_duplicate_child_absence_same_case_day_blocked():
    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        day = today_ist()
        _clear_case_day(db, therapist.id, shadow.id, day)
        first = _add_session(db, case_id=shadow.id, therapist_id=therapist.id, day=day)
        second = _add_session(
            db,
            case_id=shadow.id,
            therapist_id=therapist.id,
            day=day,
            status=SessionStatus.SCHEDULED,
        )
        second.start_time = time(11, 0)
        second.end_time = time(12, 0)
        db.commit()
        absence.create_request(
            db, therapist, first.id, absence_type="CLIENT_ABSENT", reason="Unwell"
        )
        db.commit()
        with pytest.raises(HTTPException) as exc:
            absence.create_request(
                db, therapist, second.id, absence_type="CLIENT_ABSENT", reason="Still unwell"
            )
        assert exc.value.status_code == 409
    finally:
        db.close()


def test_child_absence_reuses_cancelled_session_same_day():
    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        day = today_ist()
        _clear_case_day(db, therapist.id, shadow.id, day)
        cancelled = _add_session(
            db,
            case_id=shadow.id,
            therapist_id=therapist.id,
            day=day,
            status=SessionStatus.CANCELLED,
        )
        db.commit()
        created = absence.create_request(
            db, therapist, cancelled.id, absence_type="CLIENT_ABSENT", reason="Disposition day"
        )
        db.commit()
        assert created["session_id"] == cancelled.id
        assert created["status"] == SessionAbsenceStatus.PENDING_APPROVAL.value
    finally:
        db.close()


def test_leave_then_child_absence_same_case_day_blocked():
    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        day = today_ist()
        _clear_case_day(db, therapist.id, shadow.id, day)
        leave_service.create_therapist_leave_request(
            db,
            therapist=therapist,
            start_date=day,
            end_date=day,
            case_ids=[shadow.id],
            auto_approve=True,
            reviewer_user_id=therapist.id,
        )
        session = _add_session(db, case_id=shadow.id, therapist_id=therapist.id, day=day)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            absence.create_request(db, therapist, session.id, absence_type="CLIENT_ABSENT")
        assert exc.value.status_code == 409
        assert "leave" in str(exc.value.detail).lower()
    finally:
        db.close()


def test_child_absence_then_leave_same_case_day_blocked():
    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        day = today_ist()
        _clear_case_day(db, therapist.id, shadow.id, day)
        session = _add_session(db, case_id=shadow.id, therapist_id=therapist.id, day=day)
        db.commit()
        absence.create_request(db, therapist, session.id, absence_type="CLIENT_ABSENT")
        db.commit()
        with pytest.raises(ValueError, match="child absence"):
            leave_service.create_therapist_leave_request(
                db,
                therapist=therapist,
                start_date=day,
                end_date=day,
                case_ids=[shadow.id],
                auto_approve=True,
                reviewer_user_id=therapist.id,
            )
    finally:
        db.close()


def test_shadow_fri_mon_counts_only_scheduled_days():
    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        _add_session(db, case_id=shadow.id, therapist_id=therapist.id, day=FRI)
        _add_session(db, case_id=shadow.id, therapist_id=therapist.id, day=MON)
        leave = TherapistLeave(
            therapist_user_id=therapist.id,
            leave_type=LeaveType.UNPAID,
            service_line="shadow_support",
            billing_category=LeaveBillingCategory.UNPAID,
            includes_shadow_cases=True,
            case_id=shadow.id,
            case_ids=[shadow.id],
            paid_days=0,
            unpaid_days=2,
            start_date=FRI,
            end_date=MON,
            status=LeaveStatus.APPROVED,
        )
        db.add(leave)
        db.commit()

        dates = leave_dates.billable_leave_dates(db, leave, case_id=shadow.id)
        assert dates == [FRI, MON]
        assert SAT not in dates
        assert SUN not in dates

        lines = attendance.build_leave_lines_for_case(
            db, case=shadow, leaves=[leave], month_start=date(2026, 3, 1), month_end=date(2026, 3, 31)
        )
        line_days = {row["session_date"] for row in lines}
        assert line_days == {FRI.isoformat(), MON.isoformat()}
        assert SAT.isoformat() not in line_days

        counts = attendance.leave_days_in_month_for_case(db, therapist.id, shadow.id, "2026-03")
        assert counts["unpaid"] >= 2
    finally:
        db.close()


def test_saturday_with_booked_session_counts():
    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        _add_session(db, case_id=shadow.id, therapist_id=therapist.id, day=SAT)
        leave = TherapistLeave(
            therapist_user_id=therapist.id,
            leave_type=LeaveType.UNPAID,
            service_line="shadow_support",
            billing_category=LeaveBillingCategory.UNPAID,
            includes_shadow_cases=True,
            case_id=shadow.id,
            case_ids=[shadow.id],
            paid_days=0,
            unpaid_days=1,
            start_date=SAT,
            end_date=SAT,
            status=LeaveStatus.APPROVED,
        )
        db.add(leave)
        db.commit()
        assert leave_dates.billable_leave_dates(db, leave, case_id=shadow.id) == [SAT]
    finally:
        db.close()


def test_missing_employment_start_leaves_all_unpaid():
    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        profile = _ensure_therapist_profile(db, therapist.id)
        profile.employment_start_date = None
        db.commit()

        _add_session(db, case_id=shadow.id, therapist_id=therapist.id, day=FRI)
        _add_session(db, case_id=shadow.id, therapist_id=therapist.id, day=MON)
        bal = policy.get_leave_balance(db, therapist, year=2026, as_of=date(2026, 6, 18))
        assert bal["balance_updated"] is False
        assert bal["credits_earned"] == 0

        split = policy.suggest_leave_split(
            db,
            therapist,
            start_date=FRI,
            end_date=MON,
            service_line="shadow_support",
            case_ids=[shadow.id],
        )
        assert split.paid_days == 0
        assert split.unpaid_days == 2
    finally:
        db.close()


def test_late_session_overlap_messages():
    from app.services import invoice_billing_service as billing

    db = SessionLocal()
    try:
        therapist, shadow, _ = _therapist_cases(db)
        if not shadow:
            pytest.skip("Need a shadow case")
        day = date(2026, 2, 10)
        live = _add_session(
            db,
            case_id=shadow.id,
            therapist_id=therapist.id,
            day=day,
            status=SessionStatus.IN_PROGRESS,
        )
        db.commit()
        with pytest.raises(ValueError, match="already in progress"):
            billing.create_late_session(
                db,
                therapist.id,
                case_id=shadow.id,
                month="2026-02",
                session_date=day,
                start_time=time(9, 15),
                end_time=time(10, 15),
                attendance_status="PRESENT",
                activities_done="Overlap",
                observations=None,
                late_reason="Forgot to log after overlap",
            )
        live.status = SessionStatus.SCHEDULED
        db.commit()
        with pytest.raises(ValueError, match="Edit the time or cancel"):
            billing.create_late_session(
                db,
                therapist.id,
                case_id=shadow.id,
                month="2026-02",
                session_date=day,
                start_time=time(9, 15),
                end_time=time(10, 15),
                attendance_status="PRESENT",
                activities_done="Overlap",
                observations=None,
                late_reason="Forgot to log after overlap",
            )
    finally:
        db.close()
